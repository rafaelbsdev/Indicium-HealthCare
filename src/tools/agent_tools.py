from langchain_core.tools import tool
import agregados
from tools.news_tool import buscar_noticias, noticias_como_texto

_ULTIMO = {}


@tool(description="Calcula as 4 métricas oficiais de SRAG a partir do banco de dados "
                  "(aumento de casos, mortalidade, ocupação de UTI, vacinação). "
                  "Retorna valores já calculados; não estime números.")
def consultar_metricas():
    res = agregados.calcular_metricas()
    _ULTIMO["metricas"] = res
    linhas = [f"Data de referência: {res.data_referencia.date()}",
              f"Casos nos últimos 12 meses: {res.total_casos}"]
    linhas += [m.resumo() for m in res.metricas.values()]
    return "\n".join(linhas)


@tool(description="Gera os gráficos do relatório (casos diários e mensais, faixa etária, "
                  "classificação final e por estado) e confirma a geração.")
def gerar_graficos():
    s = agregados.series_graficos()
    return ("Gráficos gerados para a data de referência "
            f"{s['ref'].date()}: casos diários (30 dias), casos mensais (12 meses), "
            "casos e óbitos por faixa etária, casos por classificação final e casos por estado.")


@tool(description="Busca manchetes recentes de SRAG na internet em tempo real, "
                  "para contextualizar as métricas com o cenário atual.")
def consultar_noticias():
    try:
        return noticias_como_texto(buscar_noticias())
    except Exception as e:
        return f"Não foi possível recuperar notícias agora ({e})."


TODAS_AS_TOOLS = [consultar_metricas, gerar_graficos, consultar_noticias]
