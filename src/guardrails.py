import re
from dataclasses import dataclass


@dataclass
class ResultadoGuardrail:
    aprovado: bool
    motivo: str = ""


@dataclass
class ResultadoConteudoExterno:
    texto: str
    alterado: bool = False


TERMOS_NO_ESCOPO = ["srag","síndrome respiratória","sindrome respiratoria","gripe",
    "influenza","covid","surto","internação","internacao","uti","óbito","obito",
    "mortalidade","vacina","caso","relatório","relatorio","saúde","saude","epidem"]


def validar_escopo(pergunta):
    p = pergunta.lower()
    if any(t in p for t in TERMOS_NO_ESCOPO):
        return ResultadoGuardrail(True)
    return ResultadoGuardrail(False,
        "Pergunta fora do escopo: este agente só trata de SRAG e saúde pública.")


def validar_numeros_do_texto(texto, valores_permitidos, tolerancia=0.1):
    for bruto in re.findall(r"(\d+[.,]?\d*)\s*%", texto):
        valor = float(bruto.replace(",", "."))
        if not any(abs(abs(valor) - abs(v)) <= tolerancia for v in valores_permitidos):
            return ResultadoGuardrail(False,
                f"A análise citou {bruto}% que não confere com nenhuma das métricas "
                f"oficiais calculadas.")
    return ResultadoGuardrail(True)


PADRAO_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
PADRAO_CNS = re.compile(r"\b\d{3}\s?\d{4}\s?\d{4}\s?\d{4}\b")
PADRAO_TELEFONE = re.compile(r"(?:\+55\s?)?\(?\d{2}\)?\s?9\d{4}[-\s]?\d{4}\b")
PADRAO_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PADRAO_NOME = re.compile(r"\bpaciente\s+[A-ZÁÉÍÓÚ][a-záéíóú]+\s+[A-ZÁÉÍÓÚ]", re.UNICODE)

IDENTIFICADORES = [(PADRAO_CPF, "CPF"), (PADRAO_CNS, "CNS"),
                   (PADRAO_TELEFONE, "telefone"), (PADRAO_EMAIL, "e-mail")]


def validar_sem_dado_sensivel(texto):
    for padrao, nome in IDENTIFICADORES:
        if padrao.search(texto):
            return ResultadoGuardrail(False, f"Saída contém algo com formato de {nome}.")
    if PADRAO_NOME.search(texto):
        return ResultadoGuardrail(False, "Saída parece citar nome de paciente.")
    return ResultadoGuardrail(True)


def sanitizar_saida(texto):
    for padrao, _ in IDENTIFICADORES:
        texto = padrao.sub("[dado removido]", texto)
    return texto


PADROES_INJECAO = [
    re.compile(r"(?i)ignore\s+(as\s+|todas\s+as\s+)?(instruções|previous\s+instructions|prompts?)"),
    re.compile(r"(?i)desconsidere\s+(as\s+)?(instruções|regras|mensagens\s+anteriores|anteriores)"),
    re.compile(r"(?i)disregard\s+(all\s+)?(previous|prior)\s+(instructions?|prompts?)"),
    re.compile(r"(?i)(você\s+agora\s+é|you\s+are\s+now|a\s+partir\s+de\s+agora\s+você)"),
    re.compile(r"(?im)^\s*(system|assistant|user|sistema|assistente)\s*:"),
    re.compile(r"(?i)(nova\s+instrução|new\s+instructions?|override)"),
]


def sanitizar_conteudo_externo(texto):
    alterado = False
    limpo = texto
    if "```" in limpo or "<" in limpo or ">" in limpo:
        alterado = True
        limpo = limpo.replace("```", " ")
        limpo = re.sub(r"[<>]", " ", limpo)
    for padrao in PADROES_INJECAO:
        if padrao.search(limpo):
            alterado = True
            limpo = padrao.sub("[trecho removido]", limpo)
    limpo = re.sub(r"\s+", " ", limpo).strip()
    return ResultadoConteudoExterno(limpo, alterado)
