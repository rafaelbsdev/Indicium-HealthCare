import pandas as pd
import pytest
import metrics, charts, agregados


def _refs(df_limpo):
    return [df_limpo["DATA_CASO"].max(), pd.Timestamp("2024-05-01")]


def test_metricas_paridade_com_linhas_cruas(db_temporario, df_limpo):
    for ref in _refs(df_limpo):
        raw = metrics.calcular_todas(df_limpo, ref=ref)
        agg = agregados.calcular_metricas(ref=ref)
        assert agg.data_referencia == raw.data_referencia
        assert agg.total_casos == raw.total_casos
        assert set(agg.metricas) == set(raw.metricas)
        for k in raw.metricas:
            r, a = raw.metricas[k], agg.metricas[k]
            assert a.nome == r.nome
            assert (a.valor is None) == (r.valor is None)
            if r.valor is not None:
                assert a.valor == pytest.approx(r.valor)
            assert (a.numerador, a.denominador) == (r.numerador, r.denominador)
            assert a.detalhe == r.detalhe


def test_ref_padrao_e_a_data_mais_recente(db_temporario, df_limpo):
    assert agregados.calcular_metricas().data_referencia == df_limpo["DATA_CASO"].max()


def test_intervalo_datas_bate(db_temporario, df_limpo):
    mn, mx = agregados.intervalo_datas()
    assert mn == df_limpo["DATA_CASO"].min() and mx == df_limpo["DATA_CASO"].max()


def test_series_graficos_paridade(db_temporario, df_limpo):
    ref = df_limpo["DATA_CASO"].max()
    s = agregados.series_graficos(ref=ref)
    assert list(s["diario"].values) == list(charts._serie_diaria(df_limpo, ref).values)
    assert list(s["mensal"].values) == list(charts._serie_mensal(df_limpo, ref).values)
    casos_f, obitos_f = charts._serie_faixa(df_limpo, ref)
    assert list(s["faixa_casos"].values) == list(casos_f.values)
    assert list(s["faixa_obitos"].values) == list(obitos_f.values)
    assert int(s["virus"].sum()) == int(charts._serie_virus(df_limpo, ref).sum())
    assert int(s["uf"].sum()) == int(charts._serie_uf(df_limpo, ref).sum())


def test_gerar_graficos_devolve_5_png(db_temporario):
    g = agregados.gerar_graficos()
    assert set(g) == {"diario", "mensal", "faixa_etaria", "tipo_virus", "geografico"}
    assert all(isinstance(v, bytes) and v[:8] == b"\x89PNG\r\n\x1a\n" for v in g.values())
