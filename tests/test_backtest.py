import pandas as pd
import pytest
import metrics


def _dados():
    ref = pd.Timestamp("2025-06-30")
    datas = [ref - pd.Timedelta(days=d) for d in [1, 2, 40, 41, 200]]
    df = pd.DataFrame({
        "DATA_CASO": pd.to_datetime(datas),
        "EVOLUCAO": ["2", "1", "2", "1", "9"],   # desfecho conhecido=4, óbitos=2 -> 50%
        "UTI": ["1", "2", "1", "2", "1"],          # conhecido=5, UTI=3 -> 60%
        "VACINA_COV": [None] * 5,
        "VACINA": ["1", "1", "2", "2", "1"],       # gripe: conhecido=5, sim=3 -> 60%
        "SG_UF_NOT": ["SP"] * 5, "CLASSI_FIN": ["5"] * 5,
        "IDADE_ANOS": [30, 40, 50, 60, 70],
    })
    return df, ref


def test_backtest_valores_conferidos_a_mao():
    df, ref = _dados()
    res = metrics.calcular_todas(df, ref=ref)
    assert res.total_casos == 5
    assert res.metricas["aumento_casos"].valor == pytest.approx(0.0)     # 2 vs 2
    assert res.metricas["mortalidade"].valor == pytest.approx(50.0)      # 2/4
    assert res.metricas["ocupacao_uti"].valor == pytest.approx(60.0)     # 3/5
    assert res.metricas["vacinacao"].valor == pytest.approx(60.0)        # gripe 3/5
