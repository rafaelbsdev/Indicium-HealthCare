from langchain_core.tools import tool
import metrics, charts
from tools.news_tool import buscar_noticias, noticias_como_texto

_ULTIMO = {}


@tool(description="Calcula as 4 métricas oficiais de SRAG a partir do banco de dados "
                  "(aumento de casos, mortalidade, ocupação de UTI, vacinação). "
                  "Retorna valores já calculados; não estime números.")
def consultar_metricas():
    res = metrics.calcular_todas()
    _ULTIMO["metricas"] = res
    linhas = [f"Data de referência: {res.data_referencia.date()}",
              f"Casos nos últimos 12 meses: {res.total_casos}"]
    linhas += [m.resumo() for m in res.metricas.values()]
    return "\n".join(linhas)


@tool(description="Gera os dois gráficos exigidos (casos diários dos últimos 30 dias e "
                  "casos mensais dos últimos 12 meses) e retorna os caminhos dos PNGs.")
def gerar_graficos():
    df = metrics.carregar_dados()
    ref = metrics.definir_data_referencia(df)
    c = charts.gerar_todos(df, ref)
    return f"Gráfico diário: {c['diario']}\nGráfico mensal: {c['mensal']}"


@tool(description="Busca manchetes recentes de SRAG na internet em tempo real, "
                  "para contextualizar as métricas com o cenário atual.")
def consultar_noticias():
    try:
        return noticias_como_texto(buscar_noticias())
    except Exception as e:
        return f"Não foi possível recuperar notícias agora ({e})."


TODAS_AS_TOOLS = [consultar_metricas, gerar_graficos, consultar_noticias]
