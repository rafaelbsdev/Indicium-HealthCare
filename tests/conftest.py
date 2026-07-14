import sqlite3
import pandas as pd
import pytest

REF = pd.Timestamp("2024-06-15")


@pytest.fixture
def ref():
    return REF


@pytest.fixture
def df_limpo():
    datas = [REF - pd.Timedelta(days=d) for d in (1,3,10,15,20,28, 33,40,50,58)]
    return pd.DataFrame({
        "DATA_CASO": pd.to_datetime(datas),
        "DT_SIN_PRI": pd.to_datetime(datas),
        "EVOLUCAO":  ["2","2","3","1","1","1","1","1","9",None],
        "UTI":       ["1","1","1","2","2","2","2","2",None,"9"],
        "VACINA_COV": [None]*10,
        "VACINA":    ["1","1","1","1","2","2","2","2","2",None],
        "HOSPITAL":  ["1"]*10,
        "CLASSI_FIN":["5","5","4","1","1","2","2","4","5","1"],
        "SG_UF_NOT": ["SP","SP","RJ","RJ","MG","MG","SP","SP","RJ","MG"],
        "CS_SEXO":   ["F","M","F","M","F","M","F","M","F","M"],
        "IDADE_ANOS":[72, 5, 88, 34, 45, 60, 25, 15, 0, 90],
    })


@pytest.fixture
def db_temporario(tmp_path, df_limpo, monkeypatch):
    import metrics, data_pipeline, agregados
    db = tmp_path / "t.db"
    enriquecido = data_pipeline.enriquecer(df_limpo.copy())
    with sqlite3.connect(db) as c:
        enriquecido.to_sql("srag", c, if_exists="replace", index=False)
        data_pipeline.construir_agregados(c)
    monkeypatch.setattr(metrics, "DB_PATH", db)
    monkeypatch.setattr(data_pipeline, "DB_PATH", db)
    monkeypatch.setattr(agregados, "DB_PATH", db)
    return db


@pytest.fixture
def pastas_temporarias(tmp_path, monkeypatch):
    import audit
    l = tmp_path / "logs"; l.mkdir()
    monkeypatch.setattr(audit, "LOGS_DIR", l)
    return {"logs": l}
