import re
import urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Noticia:
    titulo: str
    fonte: str
    data: str
    link: str

    def linha(self):
        return f"- {self.titulo} ({self.fonte}, {self.data})"


def montar_url(consulta):
    return f"https://news.google.com/rss/search?q={urllib.parse.quote(consulta)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"


def _baixar_rss(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _parse_rss(xml_bruto, max_itens=5):
    raiz = ET.fromstring(xml_bruto)
    noticias = []
    for item in list(raiz.iterfind(".//item"))[:max_itens]:
        titulo = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        fe = item.find("source")
        if fe is None:
            fe = item.find("{http://news.google.com}source")
        fonte = fe.text.strip() if fe is not None and fe.text else "Google Notícias"
        try:
            data = datetime.strptime(pub[:16], "%a, %d %b %Y").strftime("%Y-%m-%d")
        except Exception:
            data = pub or "data desconhecida"
        if fonte and titulo.endswith(f" - {fonte}"):
            titulo = titulo[: -(len(fonte) + 3)].strip()
        noticias.append(Noticia(titulo, fonte, data, link))
    return noticias


CONSULTAS = ["SRAG síndrome respiratória aguda grave",
             "InfoGripe Fiocruz síndrome respiratória",
             "surto vírus respiratório Brasil"]


def _normalizar_titulo(titulo):
    return re.sub(r"\s+", " ", titulo.lower()).strip()


def deduplicar(noticias):
    vistos, saida = set(), []
    for n in noticias:
        chave = _normalizar_titulo(n.titulo) or n.link
        if chave and chave not in vistos:
            vistos.add(chave)
            saida.append(n)
    return saida


def buscar_noticias(consultas=None, max_itens=10, timeout=10):
    if consultas is None:
        consultas = CONSULTAS
    if isinstance(consultas, str):
        consultas = [consultas]
    todas = []
    for consulta in consultas:
        try:
            todas.extend(_parse_rss(_baixar_rss(montar_url(consulta), timeout=timeout), max_itens=max_itens))
        except Exception:
            continue
    return ordenar_por_data(deduplicar(todas))[:max_itens]


def noticias_como_texto(noticias):
    if not noticias:
        return "Nenhuma notícia recente foi recuperada."
    return "\n".join(n.linha() for n in noticias)


def noticias_como_html(noticias):
    if not noticias:
        return "Nenhuma notícia recente foi recuperada."
    itens = "".join(
        f'<li class="nt-item">{n.titulo} — '
        f'<a href="{n.link}" target="_blank" rel="noopener noreferrer">{n.fonte}</a>'
        f' · {n.data}</li>'
        for n in noticias)
    return f'<ul class="noticias">{itens}</ul>'


def ordenar_por_data(noticias):
    from datetime import datetime
    def chave(n):
        try:
            return (1, datetime.strptime(n.data, "%Y-%m-%d"))
        except Exception:
            return (0, datetime.min)
    return sorted(noticias, key=chave, reverse=True)
