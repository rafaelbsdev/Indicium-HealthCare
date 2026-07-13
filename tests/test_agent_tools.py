import pytest
pytest.importorskip("langchain_core")
from tools import agent_tools  # noqa: E402


def test_tool_metricas(db_temporario):
    s = agent_tools.consultar_metricas.invoke({})
    assert "Data de referência" in s and "Taxa de mortalidade" in s

def test_tool_noticias_mockada(monkeypatch):
    from tools.news_tool import Noticia
    monkeypatch.setattr(agent_tools, "buscar_noticias", lambda *a, **k: [Noticia("T","F","2024-07-10","http://x")])
    assert "T" in agent_tools.consultar_noticias.invoke({})

def test_tool_noticias_trata_erro(monkeypatch):
    def boom(*a, **k): raise RuntimeError("sem rede")
    monkeypatch.setattr(agent_tools, "buscar_noticias", boom)
    assert "não foi possível" in agent_tools.consultar_noticias.invoke({}).lower()
