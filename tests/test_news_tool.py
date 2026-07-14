from tools import news_tool

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item><title>Casos de SRAG sobem em SP</title><link>http://ex.com/1</link>
    <pubDate>Wed, 10 Jul 2024 12:00:00 GMT</pubDate><source url="http://g1.com">G1</source></item>
  <item><title>Alerta de influenza</title><link>http://ex.com/2</link>
    <pubDate>Tue, 09 Jul 2024 08:30:00 GMT</pubDate><source url="http://folha.com">Folha</source></item>
</channel></rss>"""

def test_parse_extrai_titulo_e_fonte():
    n = news_tool._parse_rss(RSS)
    assert len(n) == 2 and n[0].titulo == "Casos de SRAG sobem em SP" and n[0].fonte == "G1"

def test_parse_normaliza_data():
    assert news_tool._parse_rss(RSS)[0].data == "2024-07-10"

def test_parse_respeita_max():
    assert len(news_tool._parse_rss(RSS, max_itens=1)) == 1

def test_texto_vazio():
    assert "Nenhuma notícia" in news_tool.noticias_como_texto([])

def test_texto_formata():
    assert "Casos de SRAG" in news_tool.noticias_como_texto(news_tool._parse_rss(RSS))

def test_buscar_usa_parsing_sem_rede(monkeypatch):
    monkeypatch.setattr(news_tool, "_baixar_rss", lambda url, timeout=10: RSS)
    assert len(news_tool.buscar_noticias("x")) == 2


def test_noticias_como_html_tem_link_na_fonte():
    n = news_tool.Noticia("Casos sobem", "G1", "2024-07-10", "https://g1.com/materia")
    html = news_tool.noticias_como_html([n])
    assert 'href="https://g1.com/materia"' in html
    assert "G1" in html and "Casos sobem" in html
    assert "target=\"_blank\"" in html  # abre em nova aba


def test_noticias_como_html_vazio():
    assert "Nenhuma notícia" in news_tool.noticias_como_html([])


RSS_SUFIXO = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item><title>Casos sobem em SP - G1</title><link>http://ex.com/1</link>
    <pubDate>Wed, 10 Jul 2024 12:00:00 GMT</pubDate><source url="http://g1.com">G1</source></item>
</channel></rss>"""


def test_parse_remove_sufixo_da_fonte_no_titulo():
    n = news_tool._parse_rss(RSS_SUFIXO)[0]
    assert n.titulo == "Casos sobem em SP"   # sem "- G1"
    assert n.fonte == "G1"


def test_ordenar_por_data_desc():
    ns = [news_tool.Noticia("a", "F", "2024-07-01", "x"),
          news_tool.Noticia("b", "F", "2024-07-10", "x"),
          news_tool.Noticia("c", "F", "2024-07-05", "x")]
    datas = [n.data for n in news_tool.ordenar_por_data(ns)]
    assert datas == ["2024-07-10", "2024-07-05", "2024-07-01"]


def test_buscar_noticias_ate_10(monkeypatch):
    itens = "".join(
        f'<item><title>N{i}</title><link>http://x/{i}</link>'
        f'<pubDate>Wed, 10 Jul 2024 12:00:00 GMT</pubDate>'
        f'<source url="http://f">F</source></item>' for i in range(12))
    rss = f'<?xml version="1.0"?><rss><channel>{itens}</channel></rss>'
    monkeypatch.setattr(news_tool, "_baixar_rss", lambda url, timeout=10: rss)
    assert len(news_tool.buscar_noticias("x")) == 10   # no máximo 10


def test_deduplica_titulos_repetidos():
    ns = [news_tool.Noticia("Casos sobem", "G1", "2024-07-10", "x"),
          news_tool.Noticia("casos  sobem", "Folha", "2024-07-09", "y")]
    assert len(news_tool.deduplicar(ns)) == 1


def test_buscar_multiplas_fontes_deduplica(monkeypatch):
    monkeypatch.setattr(news_tool, "_baixar_rss", lambda url, timeout=10: RSS)
    ns = news_tool.buscar_noticias()          # 3 consultas, mesmo RSS(2) -> dedup para 2
    assert len(ns) == 2
