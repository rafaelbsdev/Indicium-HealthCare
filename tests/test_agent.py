import metrics, agent


def _res(df):
    return metrics.calcular_todas(df)


def test_sem_api_gera_aviso_honesto(df_limpo, pastas_temporarias, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    t = agent.comentar_metricas(_res(df_limpo), "sem notícias")
    assert "indisponível" in t.lower()
    assert "ANTHROPIC_API_KEY" in t


def test_usa_texto_llm_valido(df_limpo, pastas_temporarias, monkeypatch):
    monkeypatch.setattr(agent, "_get_api_key", lambda: "fake")
    monkeypatch.setattr(agent, "_invocar_llm", lambda sp, up: "Mortalidade de 37.50%.")
    t = agent.comentar_metricas(_res(df_limpo), "ctx")
    assert "37.50%" in t and "indisponível" not in t.lower()


def test_numero_nao_verificado_mantem_analise_com_aviso(df_limpo, pastas_temporarias, monkeypatch):
    monkeypatch.setattr(agent, "_get_api_key", lambda: "fake")
    monkeypatch.setattr(agent, "_invocar_llm", lambda sp, up: "A taxa foi de 95.00% neste período.")
    t = agent.comentar_metricas(_res(df_limpo), "ctx")
    assert "95.00%" in t                       # a análise é PRESERVADA
    assert "bservação" in t                    # com uma observação sobre o número
    assert "indisponível" not in t.lower()     # e NÃO é descartada


def test_analise_valida_nao_tem_observacao(df_limpo, pastas_temporarias, monkeypatch):
    monkeypatch.setattr(agent, "_get_api_key", lambda: "fake")
    monkeypatch.setattr(agent, "_invocar_llm", lambda sp, up: "Mortalidade de 37.50%.")
    t = agent.comentar_metricas(_res(df_limpo), "ctx")
    assert "bservação" not in t and "indisponível" not in t.lower()


def test_falha_do_llm_vira_aviso(df_limpo, pastas_temporarias, monkeypatch):
    monkeypatch.setattr(agent, "_get_api_key", lambda: "fake")

    def explode(sp, up):
        raise RuntimeError("timeout")

    monkeypatch.setattr(agent, "_invocar_llm", explode)
    t = agent.comentar_metricas(_res(df_limpo), "ctx")
    assert "indisponível" in t.lower()


def test_registra_auditoria(df_limpo, pastas_temporarias, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from audit import Auditor
    a = Auditor()
    agent.comentar_metricas(_res(df_limpo), "x", a)
    assert "llm_decision" in a.caminho.read_text(encoding="utf-8")
