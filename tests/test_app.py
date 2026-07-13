import app


def test_renderizar_conteudo_cacheia_por_data(monkeypatch):
    app._CACHE.clear()
    chamadas = []
    monkeypatch.setattr(app, "construir_conteudo",
                        lambda data_ref=None: (chamadas.append(data_ref), f"c-{data_ref}")[1])
    assert app.renderizar_conteudo(data_ref="2024-05-01") == "c-2024-05-01"
    assert app.renderizar_conteudo(data_ref="2024-05-01") == "c-2024-05-01"   # cache
    assert app.renderizar_conteudo(data_ref="2024-06-01") == "c-2024-06-01"   # nova data
    assert app.renderizar_conteudo(atualizar=True, data_ref="2024-06-01") == "c-2024-06-01"
    assert chamadas == ["2024-05-01", "2024-06-01", "2024-06-01"]
