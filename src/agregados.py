import sqlite3
from datetime import timedelta
import pandas as pd
import charts
from config import (DB_PATH, AGG_DIARIO, AGG_FAIXA, AGG_UF, AGG_VIRUS, JANELA_CURTA_DIAS,
                    JANELA_LONGA_MESES, DATA_REFERENCIA, CLASSI_FIN_NOMES,
                    FAIXAS_ETARIAS_ROTULOS, TOP_UF)
from metrics import Metrica, ResultadoMetricas


def _carregar(tabela):
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql(f"SELECT * FROM {tabela}", conn, parse_dates=["DATA_CASO"])


def intervalo_datas():
    d = _carregar(AGG_DIARIO)
    return d["DATA_CASO"].min(), d["DATA_CASO"].max()


def _definir_ref(d, ref):
    if ref is not None:
        return pd.Timestamp(ref)
    return pd.Timestamp(DATA_REFERENCIA) if DATA_REFERENCIA else d["DATA_CASO"].max()


def _janela(d, ref, meses):
    inicio = ref - pd.DateOffset(months=meses)
    return d[(d["DATA_CASO"] > inicio) & (d["DATA_CASO"] <= ref)]


def _aumento(d, ref, janela_dias):
    ia = ref - timedelta(days=janela_dias)
    ip = ia - timedelta(days=janela_dias)
    ca = int(d[(d["DATA_CASO"] > ia) & (d["DATA_CASO"] <= ref)]["casos"].sum())
    cp = int(d[(d["DATA_CASO"] > ip) & (d["DATA_CASO"] <= ia)]["casos"].sum())
    if cp == 0:
        return Metrica("Taxa de aumento de casos", None, "%", ca, cp, "janela anterior sem casos")
    return Metrica("Taxa de aumento de casos", (ca-cp)/cp*100, "%", ca, cp,
                   f"{ca} casos nos últimos {janela_dias}d vs {cp} nos {janela_dias}d anteriores")


def _mortalidade(jan):
    ob = int(jan["obitos"].sum()); t = int(jan["desfecho"].sum())
    if t == 0:
        return Metrica("Taxa de mortalidade", None, "%", ob, t, "sem casos com desfecho conhecido")
    return Metrica("Taxa de mortalidade", ob/t*100, "%", ob, t, f"{ob} óbitos em {t} casos encerrados")


def _uti(jan):
    fu = int(jan["uti_sim"].sum()); t = int(jan["uti_conhecido"].sum())
    if t == 0:
        return Metrica("Taxa de ocupação de UTI", None, "%", fu, t, "sem status de UTI conhecido")
    return Metrica("Taxa de ocupação de UTI", fu/t*100, "%", fu, t,
                   f"{fu} casos em UTI de {t} com status conhecido")


def _vacinacao(jan, total):
    vc = int(jan["vaccov_sim"].sum()); tc = int(jan["vaccov_conhecido"].sum())
    if tc >= 0.01 * total:
        vac, t, fonte = vc, tc, "COVID-19"
    else:
        vac = int(jan["vacgripe_sim"].sum()); t = int(jan["vacgripe_conhecido"].sum()); fonte = "gripe"
    if t == 0:
        return Metrica("Taxa de vacinação", None, "%", vac, t, "sem status de vacinação conhecido")
    return Metrica("Taxa de vacinação", vac/t*100, "%", vac, t,
                   f"{vac} vacinados ({fonte}) de {t} com status conhecido")


def calcular_metricas(ref=None, janela_longa_meses=JANELA_LONGA_MESES, janela_dias=JANELA_CURTA_DIAS):
    d = _carregar(AGG_DIARIO)
    ref = _definir_ref(d, ref)
    jan = _janela(d, ref, janela_longa_meses)
    total = int(jan["casos"].sum())
    res = ResultadoMetricas(ref, total)
    res.metricas = {
        "aumento_casos": _aumento(d, ref, janela_dias),
        "mortalidade": _mortalidade(jan),
        "ocupacao_uti": _uti(jan),
        "vacinacao": _vacinacao(jan, total),
    }
    return res


def series_graficos(ref=None, janela_dias=JANELA_CURTA_DIAS, janela_meses=JANELA_LONGA_MESES, top=TOP_UF):
    d = _carregar(AGG_DIARIO)
    ref = _definir_ref(d, ref)

    inicio_d = ref - pd.Timedelta(days=janela_dias)
    jd = d[(d["DATA_CASO"] > inicio_d) & (d["DATA_CASO"] <= ref)]
    s_dia = jd.set_index("DATA_CASO")["casos"].reindex(
        pd.date_range(inicio_d + pd.Timedelta(days=1), ref, freq="D"), fill_value=0)

    jm = _janela(d, ref, janela_meses).copy()
    jm["MES"] = jm["DATA_CASO"].dt.to_period("M")
    inicio_m = ref - pd.DateOffset(months=janela_meses)
    s_mes = jm.groupby("MES")["casos"].sum().reindex(
        pd.period_range((inicio_m + pd.Timedelta(days=1)).to_period("M"), ref.to_period("M"), freq="M"), fill_value=0)

    f = _janela(_carregar(AGG_FAIXA), ref, janela_meses)
    casos_f = f.groupby("FAIXA")["casos"].sum().reindex(FAIXAS_ETARIAS_ROTULOS, fill_value=0)
    obitos_f = f.groupby("FAIXA")["obitos"].sum().reindex(FAIXAS_ETARIAS_ROTULOS, fill_value=0)

    v = _janela(_carregar(AGG_VIRUS), ref, janela_meses)
    cont_v = v.groupby("classi")["casos"].sum()
    cont_v = cont_v.rename(index=lambda c: CLASSI_FIN_NOMES.get(c, "Não informado"))
    cont_v = cont_v.groupby(level=0).sum().sort_values()

    u = _janela(_carregar(AGG_UF), ref, janela_meses)
    cont_u = u.groupby("uf")["casos"].sum().sort_values(ascending=False).head(top).sort_values()

    return {"diario": s_dia, "mensal": s_mes, "faixa_casos": casos_f, "faixa_obitos": obitos_f,
            "virus": cont_v, "uf": cont_u, "ref": ref}


def gerar_graficos(ref=None):
    s = series_graficos(ref)
    ref = s["ref"]
    return {"diario": charts.render_diario(s["diario"], ref),
            "mensal": charts.render_mensal(s["mensal"], ref),
            "faixa_etaria": charts.render_faixa(s["faixa_casos"], s["faixa_obitos"], ref),
            "tipo_virus": charts.render_virus(s["virus"], ref),
            "geografico": charts.render_geografico(s["uf"], ref)}
