import sqlite3
import pandas as pd
import data_pipeline


def _df_cru():
    return pd.DataFrame({
        "DT_SIN_PRI": ["2024-01-10T00:00:00.000Z","2024-02-15T00:00:00.000Z", None],
        "DT_NOTIFIC": ["2024-01-11T00:00:00.000Z"]*3,
        "DT_INTERNA": ["2109-07-10T00:00:00.000Z","2024-02-16T00:00:00.000Z","2024-01-01T00:00:00.000Z"],
        "DT_ENTUTI": [None]*3, "DT_SAIDUTI": [None]*3, "DT_EVOLUCA": [None]*3,
        "EVOLUCAO": ["2.0","1.0","1.0"], "UTI": ["1","2","2"],
        "VACINA": ["1","2","9"], "VACINA_COV": [None]*3, "HOSPITAL": ["1"]*3,
        "CLASSI_FIN": ["5.0","4.0","1.0"], "SG_UF_NOT": ["SP","RJ","MG"], "CS_SEXO": ["F","M","F"],
        "DT_NASC": ["1984-01-02T00:00:00.000Z","2023-10-05T00:00:00.000Z","1998-03-03T00:00:00.000Z"],
        "NU_IDADE_N": ["40","4","26"], "TP_IDADE": ["3","2","3"],
        "PAC_COCBO": ["223505","999","111"], "PAC_DSCBO": ["Medico","Outro","Eng"],
    })


def test_remove_registro_sem_data_sintomas():
    assert len(data_pipeline.limpar(_df_cru())) == 2

def test_normaliza_codigos_ponto_zero():
    df = data_pipeline.limpar(_df_cru())
    assert set(df["EVOLUCAO"].dropna()).issubset({"1","2","3","9"})
    assert not df["EVOLUCAO"].dropna().str.contains(r"\.0").any()

def test_descarta_data_impossivel():
    df = data_pipeline.limpar(_df_cru())
    assert df["DT_INTERNA"].max() < pd.Timestamp("2100-01-01")

def test_cria_coluna_data_caso():
    df = data_pipeline.limpar(_df_cru())
    assert "DATA_CASO" in df.columns and (df["DATA_CASO"].dt.hour == 0).all()


def test_anonimiza_nascimento_mantem_so_ano():
    df = data_pipeline.limpar(_df_cru())
    assert "DT_NASC" not in df.columns
    assert "ANO_NASC" in df.columns
    assert 1984 in set(df["ANO_NASC"].dropna())

def test_remove_ocupacao():
    df = data_pipeline.limpar(_df_cru())
    assert "PAC_COCBO" not in df.columns and "PAC_DSCBO" not in df.columns

def test_deriva_idade_em_anos():
    df = data_pipeline.limpar(_df_cru())
    idades = set(df["IDADE_ANOS"].dropna())
    assert 40 in idades
    assert 0 in idades


def test_carregar_csv_so_colunas_necessarias(tmp_path):
    p = tmp_path / "INFLUD_x.csv"
    df = _df_cru(); df["EXTRA_SENSIVEL"] = ["a","b","c"]
    df.to_csv(p, sep=";", index=False)
    out = data_pipeline.carregar_csv(p)
    assert "EXTRA_SENSIVEL" not in out.columns
    assert "EVOLUCAO" in out.columns and "DT_SIN_PRI" in out.columns

def test_listar_csvs_ordenado(tmp_path, monkeypatch):
    (tmp_path / "INFLUD20.csv").write_text("x")
    (tmp_path / "INFLUD19.csv").write_text("x")
    (tmp_path / "outro.txt").write_text("x")
    monkeypatch.setattr(data_pipeline, "RAW_CSV_DIR", tmp_path)
    monkeypatch.setattr(data_pipeline, "RAW_CSV_GLOB", "INFLUD*.csv")
    nomes = [p.name for p in data_pipeline.listar_csvs()]
    assert nomes == ["INFLUD19.csv", "INFLUD20.csv"]

def test_pipeline_concatena_varios_anos(tmp_path, monkeypatch):
    _df_cru().to_csv(tmp_path / "INFLUD19.csv", sep=";", index=False)
    _df_cru().to_csv(tmp_path / "INFLUD20.csv", sep=";", index=False)
    db = tmp_path / "multi.db"
    monkeypatch.setattr(data_pipeline, "RAW_CSV_DIR", tmp_path)
    monkeypatch.setattr(data_pipeline, "RAW_CSV_GLOB", "INFLUD*.csv")
    monkeypatch.setattr(data_pipeline, "DB_PATH", db)
    total = data_pipeline.executar_pipeline()
    assert total == 4                       # 2 válidos por arquivo, 2 arquivos
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM srag").fetchone()[0] == 4

def test_pipeline_le_em_blocos(tmp_path, monkeypatch):
    _df_cru().to_csv(tmp_path / "INFLUD19.csv", sep=";", index=False)
    db = tmp_path / "chunk.db"
    monkeypatch.setattr(data_pipeline, "RAW_CSV_DIR", tmp_path)
    monkeypatch.setattr(data_pipeline, "RAW_CSV_GLOB", "INFLUD*.csv")
    monkeypatch.setattr(data_pipeline, "CHUNKSIZE", 1)   # força vários blocos
    monkeypatch.setattr(data_pipeline, "DB_PATH", db)
    total = data_pipeline.executar_pipeline()
    assert total == 2
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM srag").fetchone()[0] == 2
