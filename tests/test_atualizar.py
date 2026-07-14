import io
import json
import sqlite3
import pandas as pd
import data_pipeline, atualizar_dados


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _opener(payload):
    return lambda req: _Resp(payload)


def _mini_csv(destino):
    pd.DataFrame({
        "DT_SIN_PRI": ["2026-01-10T00:00:00.000Z", "2026-02-15T00:00:00.000Z"],
        "EVOLUCAO": ["2", "1"], "UTI": ["1", "2"], "VACINA": ["1", "2"],
        "VACINA_COV": ["1", "2"], "CLASSI_FIN": ["5", "4"], "SG_UF_NOT": ["SP", "RJ"],
        "NU_IDADE_N": ["40", "5"], "TP_IDADE": ["3", "3"],
    }).to_csv(destino, sep=";", index=False)
    return destino


def test_resolver_url_le_ckan():
    payload = json.dumps({"result": {"url": "http://x/INFLUD25.csv"}}).encode()
    assert atualizar_dados.resolver_url("rid", abrir=_opener(payload)) == "http://x/INFLUD25.csv"


def test_baixar_arquivo_move_atomico(tmp_path):
    dest = tmp_path / "a.csv"
    atualizar_dados.baixar_arquivo("http://x", dest, abrir=_opener(b"conteudo"))
    assert dest.read_bytes() == b"conteudo"
    assert not (tmp_path / "a.csv.part").exists()


def test_atualizar_substitui_ano_e_reconstroi(tmp_path, monkeypatch):
    pasta = tmp_path / "data"; pasta.mkdir()
    (pasta / "INFLUD25-antigo.csv").write_text("velho")
    db = tmp_path / "srag.db"
    monkeypatch.setattr(data_pipeline, "RAW_CSV_DIR", pasta)
    monkeypatch.setattr(data_pipeline, "RAW_CSV_GLOB", "INFLUD*.csv")
    monkeypatch.setattr(data_pipeline, "DB_PATH", db)

    r = atualizar_dados.atualizar(
        recursos={"25": "r25"}, pasta=pasta,
        resolver=lambda rid: "http://x/" + rid,
        baixar=lambda url, destino, **k: _mini_csv(destino))

    nomes = [p.name for p in pasta.glob("INFLUD25*.csv")]
    assert nomes == ["INFLUD25-vivo.csv"]                 # antigo removido, um só por ano
    assert r["registros"] == 2
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM srag").fetchone()[0] == 2
        assert c.execute("SELECT valor FROM meta WHERE chave='construido_em'").fetchone() is not None
