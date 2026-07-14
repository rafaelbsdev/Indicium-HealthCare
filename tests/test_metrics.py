import pandas as pd
import pytest
import metrics


def test_aumento_casos(df_limpo, ref):
    m = metrics.taxa_aumento_casos(df_limpo, ref)
    assert m.valor == pytest.approx(50.0)
    assert (m.numerador, m.denominador) == (6, 4)

def test_aumento_sem_janela_anterior(df_limpo, ref):
    recentes = df_limpo[df_limpo["DATA_CASO"] > ref - pd.Timedelta(days=30)]
    assert metrics.taxa_aumento_casos(recentes, ref).valor is None

def test_mortalidade(df_limpo):
    m = metrics.taxa_mortalidade(df_limpo)
    assert m.valor == pytest.approx(37.5)
    assert (m.numerador, m.denominador) == (3, 8)

def test_mortalidade_sem_desfecho():
    m = metrics.taxa_mortalidade(pd.DataFrame({"EVOLUCAO": [None, "9"]}))
    assert m.valor is None

def test_ocupacao_uti(df_limpo):
    m = metrics.taxa_ocupacao_uti(df_limpo)
    assert m.valor == pytest.approx(37.5)

def test_vacinacao_gripe_quando_covid_ausente(df_limpo):
    m = metrics.taxa_vacinacao(df_limpo)
    assert m.valor == pytest.approx(44.4444, abs=1e-3)
    assert "gripe" in m.detalhe

def test_vacinacao_covid_quando_disponivel():
    df = pd.DataFrame({"VACINA_COV": ["1","1","2","2","1"], "VACINA": ["2"]*5})
    m = metrics.taxa_vacinacao(df)
    assert "COVID" in m.detalhe and m.valor == pytest.approx(60.0)

def test_calcular_todas(df_limpo):
    res = metrics.calcular_todas(df_limpo)
    assert set(res.metricas) == {"aumento_casos","mortalidade","ocupacao_uti","vacinacao"}
    assert res.data_referencia == df_limpo["DATA_CASO"].max()

def test_carregar_dados(db_temporario):
    df = metrics.carregar_dados()
    assert len(df) == 10 and "DATA_CASO" in df.columns


def test_calcular_todas_com_ref_explicita(df_limpo):
    ref = pd.Timestamp("2024-05-01")
    res = metrics.calcular_todas(df_limpo, ref=ref)
    assert res.data_referencia == ref


def test_wilson_em_torno_da_metade():
    lo, hi = metrics.intervalo_wilson(50, 100)
    assert lo < 50 < hi and 39 < lo < 45 and 55 < hi < 61


def test_mortalidade_tem_intervalo_de_confianca(df_limpo):
    m = metrics.calcular_todas(df_limpo).metricas["mortalidade"]
    assert m.ic_baixo is not None and m.ic_baixo < m.valor < m.ic_alto


def test_uti_via_cnes_usa_leitos(df_limpo):
    m = metrics.taxa_ocupacao_uti(df_limpo, leitos=10)
    assert m.valor == pytest.approx(30.0) and "leitos" in m.detalhe.lower()


def test_suavizar_media_movel():
    import pandas as pd
    assert list(metrics.suavizar(pd.Series([2, 4, 6]), janela=2)) == [2.0, 3.0, 5.0]
