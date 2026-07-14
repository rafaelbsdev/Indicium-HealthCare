import math
import sqlite3
from dataclasses import dataclass, field
from datetime import timedelta
import pandas as pd
from config import (DB_PATH, TABLE_NAME, DATA_REFERENCIA, JANELA_CURTA_DIAS,
                    EVOLUCAO_OBITOS, EVOLUCAO_DESFECHO_CONHECIDO, SIM, NAO)


@dataclass
class Metrica:
    nome: str
    valor: float
    unidade: str
    numerador: float = None
    denominador: float = None
    detalhe: str = ""
    ic_baixo: float = None
    ic_alto: float = None

    def resumo(self):
        if self.valor is None:
            return f"{self.nome}: indisponível ({self.detalhe})"
        return f"{self.nome}: {self.valor:.2f}{self.unidade} ({self.detalhe})"


@dataclass
class ResultadoMetricas:
    data_referencia: pd.Timestamp
    total_casos: int
    metricas: dict = field(default_factory=dict)


def intervalo_wilson(sucessos, total, z=1.96):
    if not total:
        return (None, None)
    p = sucessos / total
    denom = 1 + z * z / total
    centro = (p + z * z / (2 * total)) / denom
    margem = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return ((centro - margem) * 100, (centro + margem) * 100)


def com_intervalo(metrica):
    if metrica.valor is not None and metrica.numerador is not None and metrica.denominador:
        metrica.ic_baixo, metrica.ic_alto = intervalo_wilson(metrica.numerador, metrica.denominador)
    return metrica


def suavizar(serie, janela=7):
    return serie.rolling(janela, min_periods=1).mean()


def carregar_leitos_cnes():
    return None


def carregar_dados(desde=None):
    sql = f"SELECT * FROM {TABLE_NAME}"
    params = ()
    if desde is not None:
        sql += " WHERE DATA_CASO >= ?"
        params = (pd.Timestamp(desde).strftime("%Y-%m-%d"),)
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql(sql, conn, params=params, parse_dates=[
            "DATA_CASO","DT_SIN_PRI","DT_NOTIFIC","DT_INTERNA","DT_ENTUTI","DT_SAIDUTI","DT_EVOLUCA"])


def intervalo_datas():
    with sqlite3.connect(DB_PATH) as conn:
        mn, mx = conn.execute(f"SELECT MIN(DATA_CASO), MAX(DATA_CASO) FROM {TABLE_NAME}").fetchone()
    return pd.Timestamp(mn), pd.Timestamp(mx)


def definir_data_referencia(df):
    return pd.Timestamp(DATA_REFERENCIA) if DATA_REFERENCIA else df["DATA_CASO"].max()


def taxa_aumento_casos(df, ref, janela_dias=JANELA_CURTA_DIAS):
    ia = ref - timedelta(days=janela_dias)
    ip = ia - timedelta(days=janela_dias)
    ca = df[(df["DATA_CASO"] > ia) & (df["DATA_CASO"] <= ref)].shape[0]
    cp = df[(df["DATA_CASO"] > ip) & (df["DATA_CASO"] <= ia)].shape[0]
    if cp == 0:
        return Metrica("Taxa de aumento de casos", None, "%", ca, cp, "janela anterior sem casos")
    return Metrica("Taxa de aumento de casos", (ca-cp)/cp*100, "%", ca, cp,
                   f"{ca} casos nos últimos {janela_dias}d vs {cp} nos {janela_dias}d anteriores")


def taxa_mortalidade(df):
    cd = df[df["EVOLUCAO"].isin(EVOLUCAO_DESFECHO_CONHECIDO)]
    ob = cd[cd["EVOLUCAO"].isin(EVOLUCAO_OBITOS)].shape[0]
    t = cd.shape[0]
    if t == 0:
        return Metrica("Taxa de mortalidade", None, "%", ob, t, "sem casos com desfecho conhecido")
    return Metrica("Taxa de mortalidade", ob/t*100, "%", ob, t, f"{ob} óbitos em {t} casos encerrados")


def taxa_ocupacao_uti(df, leitos=None):
    c = df[df["UTI"].isin([SIM, NAO])]
    fu = c[c["UTI"] == SIM].shape[0]
    if leitos:
        return Metrica("Taxa de ocupação de UTI", fu/leitos*100, "%", fu, leitos,
                       f"{fu} casos em UTI para {leitos} leitos (CNES)")
    t = c.shape[0]
    if t == 0:
        return Metrica("Taxa de ocupação de UTI", None, "%", fu, t, "sem status de UTI conhecido")
    return Metrica("Taxa de ocupação de UTI", fu/t*100, "%", fu, t,
                   f"{fu} casos em UTI de {t} com status conhecido")


def taxa_vacinacao(df):
    def calc(col):
        c = df[df[col].isin([SIM, NAO])]
        return c[c[col] == SIM].shape[0], c.shape[0]
    vc, tc = calc("VACINA_COV")
    if tc >= 0.01 * len(df):
        vac, t, fonte = vc, tc, "COVID-19"
    else:
        vac, t = calc("VACINA")
        fonte = "gripe"
    if t == 0:
        return Metrica("Taxa de vacinação", None, "%", vac, t, "sem status de vacinação conhecido")
    return Metrica("Taxa de vacinação", vac/t*100, "%", vac, t,
                   f"{vac} vacinados ({fonte}) de {t} com status conhecido")


def calcular_todas(df=None, janela_longa_meses=12, ref=None):
    if df is None:
        df = carregar_dados()
    if ref is None:
        ref = definir_data_referencia(df)
    inicio = ref - pd.DateOffset(months=janela_longa_meses)
    dj = df[(df["DATA_CASO"] > inicio) & (df["DATA_CASO"] <= ref)]
    res = ResultadoMetricas(ref, int(dj.shape[0]))
    res.metricas = {"aumento_casos": taxa_aumento_casos(df, ref),
                    "mortalidade": taxa_mortalidade(dj),
                    "ocupacao_uti": taxa_ocupacao_uti(dj, carregar_leitos_cnes()),
                    "vacinacao": taxa_vacinacao(dj)}
    for chave in ("mortalidade", "ocupacao_uti", "vacinacao"):
        com_intervalo(res.metricas[chave])
    return res
