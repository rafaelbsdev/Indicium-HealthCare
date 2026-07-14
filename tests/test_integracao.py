import socketserver
import threading
import urllib.request
import app, report, rag


def test_servidor_responde_ponta_a_ponta(db_temporario, pastas_temporarias, monkeypatch):
    monkeypatch.setattr(report, "buscar_noticias", lambda *a, **k: [])
    monkeypatch.setattr(rag, "criar_embedder_padrao", lambda: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app._CACHE.clear()

    servidor = socketserver.TCPServer(("127.0.0.1", 0), app._Handler)
    porta = servidor.server_address[1]
    t = threading.Thread(target=servidor.serve_forever, daemon=True); t.start()
    try:
        pagina = urllib.request.urlopen(f"http://127.0.0.1:{porta}/", timeout=10).read().decode()
        conteudo = urllib.request.urlopen(f"http://127.0.0.1:{porta}/conteudo?data=", timeout=10).read().decode()
    finally:
        servidor.shutdown(); servidor.server_close()

    assert 'id="conteudo"' in pagina and 'type="date"' in pagina
    assert "Métricas principais" in conteudo and conteudo.count("data:image/png;base64,") == 5
