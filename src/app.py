import http.server
import socketserver
import threading
import webbrowser
from urllib.parse import urlparse, parse_qs
from report import construir_pagina, construir_conteudo

_CACHE = {}


def renderizar_conteudo(atualizar=False, data_ref=None):
    chave = data_ref or "padrao"
    if atualizar or chave not in _CACHE:
        _CACHE[chave] = construir_conteudo(data_ref=data_ref)
    return _CACHE[chave]


class _Handler(http.server.BaseHTTPRequestHandler):
    def _responder(self, corpo):
        dados = corpo.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        partes = urlparse(self.path)
        if partes.path in ("/", "/index.html"):
            self._responder(construir_pagina())
        elif partes.path == "/conteudo":
            qs = parse_qs(partes.query)
            data_ref = qs.get("data", [None])[0] or None
            atualizar = "atualizar" in qs
            self._responder(renderizar_conteudo(atualizar=atualizar, data_ref=data_ref))
        else:
            self.send_error(404)

    def log_message(self, *a):
        pass


def iniciar(porta=8000, abrir=True):
    with socketserver.TCPServer(("", porta), _Handler) as servidor:
        url = f"http://localhost:{porta}/"
        print(f"Relatório de SRAG servido em {url}  (Ctrl+C para parar)")
        if abrir:
            threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        servidor.serve_forever()


if __name__ == "__main__":
    iniciar()
