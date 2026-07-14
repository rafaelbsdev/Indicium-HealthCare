import sys
import main


def test_main_construir_banco(monkeypatch):
    chamado = {}
    import data_pipeline
    monkeypatch.setattr(data_pipeline, "executar_pipeline", lambda: chamado.setdefault("ok", True))
    monkeypatch.setattr(sys, "argv", ["main", "--construir-banco"])
    main.main()
    assert chamado.get("ok") is True


def test_main_padrao_sobe_servidor(monkeypatch):
    import app
    chamado = {}
    monkeypatch.setattr(app, "iniciar", lambda *a, **k: chamado.setdefault("ok", True))
    monkeypatch.setattr(sys, "argv", ["main"])
    main.main()
    assert chamado.get("ok") is True


def test_main_agente(monkeypatch, capsys):
    import agent

    class FakeMsg:
        content = "resposta do agente"

    class FakeAgent:
        def invoke(self, _):
            return {"messages": [FakeMsg()]}

    monkeypatch.setattr(agent, "construir_agente_react", lambda: FakeAgent())
    monkeypatch.setattr(sys, "argv", ["main", "--agente", "x"])
    main.main()
    assert "resposta do agente" in capsys.readouterr().out


def test_main_atualizar(monkeypatch):
    import atualizar_dados
    chamado = {}
    monkeypatch.setattr(atualizar_dados, "atualizar", lambda: chamado.setdefault("ok", True) or {"registros": 1})
    monkeypatch.setattr(sys, "argv", ["main", "--atualizar"])
    main.main()
    assert chamado.get("ok") is True
