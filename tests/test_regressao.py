import metrics, agent


def test_system_prompt_mantem_regras_criticas():
    p = agent.SYSTEM_PROMPT.lower()
    assert ("nunca invente" in p) or ("só cite" in p)   # anti-alucinação no prompt
    assert "contexto" in p                              # notícias só como contexto
    assert "individuais" in p                           # nunca dados individuais


def test_prompt_de_comentario_exige_valores_exatos(df_limpo, pastas_temporarias, monkeypatch):
    capturado = {}
    monkeypatch.setattr(agent, "_get_api_key", lambda: "fake")
    monkeypatch.setattr(agent, "_invocar_llm", lambda sp, up: capturado.setdefault("up", up) or "ok 37.50%")
    agent.comentar_metricas(metrics.calcular_todas(df_limpo), "ctx")
    up = capturado["up"]
    assert "VALORES EXATOS" in up and "cite a fonte" in up.lower()


def test_analise_snapshot_estavel(df_limpo, pastas_temporarias, monkeypatch):
    monkeypatch.setattr(agent, "_get_api_key", lambda: "fake")
    monkeypatch.setattr(agent, "_invocar_llm", lambda sp, up: "Mortalidade de 37.50% no período.")
    saida = agent.comentar_metricas(metrics.calcular_todas(df_limpo), "ctx")
    assert saida == "Mortalidade de 37.50% no período."   # sem observação, sem alteração


def test_tracing_liga_com_chave(monkeypatch):
    monkeypatch.setenv("LANGSMITH_API_KEY", "x")
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    assert agent.configurar_tracing() is True
    assert agent.os.environ["LANGCHAIN_TRACING_V2"] == "true"


def test_tracing_desliga_sem_chave(monkeypatch):
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    assert agent.configurar_tracing() is False
