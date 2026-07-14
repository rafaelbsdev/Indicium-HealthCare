import os
from audit import Auditor
import guardrails as gr

SYSTEM_PROMPT = """Você é um analista de vigilância epidemiológica de SRAG.
Regras: (1) só cite números presentes nas MÉTRICAS fornecidas, nunca invente;
(2) use NOTÍCIAS só como contexto; (3) nunca cite dados individuais;
(4) seja conciso, técnico e aponte incertezas."""


def _get_api_key():
    return os.environ.get("ANTHROPIC_API_KEY")


def configurar_tracing():
    chave = os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
    if chave:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ.setdefault("LANGCHAIN_PROJECT", "srag-agent")
        return True
    return False


def construir_llm(temperatura=0.2):
    configurar_tracing()
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
                         temperature=temperatura, timeout=60)


def construir_agente_react():
    from langgraph.prebuilt import create_react_agent
    from tools.agent_tools import TODAS_AS_TOOLS
    return create_react_agent(construir_llm(), TODAS_AS_TOOLS, prompt=SYSTEM_PROMPT)


def _invocar_llm(system_prompt, user_prompt):
    from langchain_core.messages import SystemMessage, HumanMessage
    r = construir_llm().invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
    return r.content if isinstance(r.content, str) else str(r.content)


def _aviso_indisponivel(motivo):
    return f"Análise indisponível. {motivo}"


def comentar_metricas(resultado, noticias_texto, auditor=None):
    auditor = auditor or Auditor()
    permitidos = {round(m.valor, 2) for m in resultado.metricas.values() if m.valor is not None}
    metricas_txt = "\n".join(m.resumo() for m in resultado.metricas.values())

    if not _get_api_key():
        auditor.decisao_llm("Sem ANTHROPIC_API_KEY: análise indisponível.")
        return _aviso_indisponivel(
            "A chave ANTHROPIC_API_KEY não está configurada. Configure-a no arquivo "
            ".env e instale as dependências para gerar a análise com o Claude.")

    prompt = (f"MÉTRICAS OFICIAIS (data {resultado.data_referencia.date()}):\n{metricas_txt}\n\n"
              f"NOTÍCIAS:\n{noticias_texto}\n\n"
              f"Interprete o cenário em 2-3 parágrafos. Use os VALORES EXATOS das "
              f"métricas acima (com as casas decimais), sem arredondar e sem "
              f"introduzir outros percentuais. Quando mencionar uma notícia, cite a fonte.")
    auditor.decisao_llm("Chamando LLM para comentar métricas.")
    try:
        texto = _invocar_llm(SYSTEM_PROMPT, prompt)
    except Exception as e:
        auditor.erro("comentar_metricas", f"Falha ao chamar o LLM: {e}")
        return _aviso_indisponivel(f"Falha ao consultar o LLM ({e}).")

    return _pos_processar_analise(texto, permitidos, auditor)


def _pos_processar_analise(texto, permitidos, auditor):
    texto = gr.sanitizar_saida(texto)
    cs = gr.validar_sem_dado_sensivel(texto)
    auditor.guardrail("dados_sensiveis", cs.aprovado, cs.motivo)
    cn = gr.validar_numeros_do_texto(texto, permitidos)
    auditor.guardrail("anti_alucinacao", cn.aprovado, cn.motivo)
    if not cn.aprovado:
        auditor.decisao_llm("Número não verificado sinalizado na análise.")
        texto += ("\n\n**Observação:** " + cn.motivo +
                  " Confira esse dado diretamente nas métricas antes de utilizá-lo.")
    return texto


def _invocar_agente(prompt):
    resposta = construir_agente_react().invoke({"messages": [("user", prompt)]})
    ultimo = resposta["messages"][-1]
    conteudo = getattr(ultimo, "content", ultimo)
    return conteudo if isinstance(conteudo, str) else str(conteudo)


def comentar_metricas_via_agente(resultado, auditor=None):
    auditor = auditor or Auditor()
    permitidos = {round(m.valor, 2) for m in resultado.metricas.values() if m.valor is not None}
    if not _get_api_key():
        auditor.decisao_llm("Sem ANTHROPIC_API_KEY: análise (agente) indisponível.")
        return _aviso_indisponivel(
            "A chave ANTHROPIC_API_KEY não está configurada. Configure-a no arquivo "
            ".env e instale as dependências para gerar a análise com o Claude.")
    prompt = (f"Gere a Análise do Cenário de SRAG para a data {resultado.data_referencia.date()}. "
              f"Use as ferramentas para obter as métricas e as notícias, cite apenas os valores "
              f"exatos retornados pelas métricas e escreva 2-3 parágrafos.")
    auditor.decisao_llm("Executando agente ReAct para a análise.")
    try:
        texto = _invocar_agente(prompt)
    except Exception as e:
        auditor.erro("comentar_metricas_via_agente", f"Falha no agente: {e}")
        return _aviso_indisponivel(f"Falha ao executar o agente ({e}).")
    return _pos_processar_analise(texto, permitidos, auditor)
