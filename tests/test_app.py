import app


def test_renderizar_conteudo_cacheia_por_data(monkeypatch):
    app._CACHE.clear()
    chamadas = []
    monkeypatch.setattr(app, "construir_conteudo",
                        lambda data_ref=None, modo="deterministico", interativo=False: (chamadas.append((data_ref, modo)), f"c-{data_ref}-{modo}")[1])
    assert app.renderizar_conteudo(data_ref="2024-05-01") == "c-2024-05-01-deterministico"
    assert app.renderizar_conteudo(data_ref="2024-05-01") == "c-2024-05-01-deterministico"   # cache
    assert app.renderizar_conteudo(data_ref="2024-06-01") == "c-2024-06-01-deterministico"   # nova data
    assert app.renderizar_conteudo(data_ref="2024-06-01", modo="agente") == "c-2024-06-01-agente"  # novo modo
    assert app.renderizar_conteudo(atualizar=True, data_ref="2024-06-01") == "c-2024-06-01-deterministico"
    assert chamadas == [("2024-05-01", "deterministico"), ("2024-06-01", "deterministico"),
                        ("2024-06-01", "agente"), ("2024-06-01", "deterministico")]
