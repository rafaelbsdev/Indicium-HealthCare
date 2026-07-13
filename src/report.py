import base64
import re
from datetime import datetime
import pandas as pd
import metrics, charts, rag
from audit import Auditor
from agent import comentar_metricas
from tools.news_tool import (buscar_noticias, noticias_como_texto,
                             noticias_como_html, ordenar_por_data)
from knowledge import DICIONARIO_CAMPOS

CONSULTA_RAG = "mortalidade UTI vacinação aumento de casos SRAG cenário atual"

_CSS = """<style>
:root{--azul:#08519c;--azul2:#2c7fb8;}
*{box-sizing:border-box}
body{font-family:-apple-system,Segoe UI,Arial,sans-serif;margin:0;background:#f4f6f9;color:#222}
header{background:linear-gradient(135deg,#08519c,#2c7fb8);color:#fff;padding:16px 28px 18px}
.cabecalho{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:flex-end}
.btn{display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:#fff;color:#08519c;
  border:none;border-radius:8px;text-decoration:none;font-weight:600;font-size:13px;cursor:pointer}
.picker{display:flex;align-items:center;gap:8px;background:rgba(255,255,255,.15);
  padding:6px 10px;border-radius:8px;font-size:13px}
.picker input{border:none;border-radius:6px;padding:5px 8px;font-size:13px}
header h1{margin:0;font-size:24px}
main{max-width:1320px;margin:0 auto;padding:24px 32px}
.meta{color:#5a6b7b;font-size:13px;margin-bottom:8px}
.aviso{background:#fff3cd;color:#7a5b00;border-radius:8px;padding:12px 16px;margin:6px 0 8px;font-size:14px}
h2{color:var(--azul);border-bottom:2px solid #e3ebf3;padding-bottom:6px;margin-top:36px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px}
.card{background:#fff;border-radius:12px;padding:18px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.card .valor{font-size:30px;font-weight:700;color:var(--azul2)}
.card .nome{font-weight:600;margin-top:4px}
.card .detalhe{font-size:12px;color:#666;margin-top:6px}
.grafico{background:#fff;border-radius:12px;padding:16px;box-shadow:0 1px 4px rgba(0,0,0,.08);margin:16px 0}
.grafico img{width:100%;display:block}
.bloco{background:#fff;border-radius:12px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.08);line-height:1.6}
.bloco a{color:var(--azul2);font-weight:600;text-decoration:none}
.bloco a:hover{text-decoration:underline}
.bloco h3{margin:.5em 0 .3em;font-size:18px;color:var(--azul)}
.bloco h4{margin:.5em 0 .3em;font-size:16px;color:var(--azul2)}
.bloco p{margin:.6em 0}
.bloco ul.noticias{margin:0;padding-left:20px}
.bloco ul.noticias li{margin:8px 0}
.paginacao{display:flex;gap:6px;align-items:center;margin-top:14px;flex-wrap:wrap}
.btn-pg{border:1px solid #cfe0f0;background:#fff;color:#08519c;border-radius:6px;padding:4px 10px;font-size:13px;cursor:pointer}
.btn-pg.ativo{background:var(--azul);color:#fff;border-color:var(--azul)}
.btn-pg:disabled{opacity:.4;cursor:default}
.nt-pos{font-size:13px;color:#08519c;font-weight:600;padding:0 8px;min-width:44px;text-align:center}
.carregando{text-align:center;color:#08519c;padding:60px 0}
.spin{width:46px;height:46px;border:5px solid #d9e6f2;border-top-color:#2c7fb8;border-radius:50%;
  margin:0 auto 14px;animation:g 1s linear infinite}
@keyframes g{to{transform:rotate(360deg)}}
footer{max-width:1320px;margin:0 auto;padding:16px 32px 40px;color:#888;font-size:12px}
</style>"""


def _img(png_bytes):
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode()


def _cards(res):
    blocos = []
    for m in res.metricas.values():
        valor = "—" if m.valor is None else f"{m.valor:.2f}{m.unidade}"
        blocos.append(
            f'<div class="card"><div class="valor">{valor}</div>'
            f'<div class="nome">{m.nome}</div>'
            f'<div class="detalhe">{m.detalhe}</div></div>')
    return "\n".join(blocos)


def _inline(t):
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)


def _md_para_html(texto):
    blocos = re.split(r"\n\s*\n", texto.strip())
    saida = []
    for b in blocos:
        b = b.strip()
        if not b:
            continue
        linhas = b.split("\n")
        if all(l.lstrip().startswith("- ") for l in linhas):
            itens = "".join(f"<li>{_inline(l.lstrip()[2:])}</li>" for l in linhas)
            saida.append(f"<ul>{itens}</ul>")
        elif b.startswith("### "):
            saida.append(f"<h4>{_inline(b[4:])}</h4>")
        elif b.startswith("## "):
            saida.append(f"<h3>{_inline(b[3:])}</h3>")
        elif b.startswith("# "):
            saida.append(f"<h3>{_inline(b[2:])}</h3>")
        else:
            saida.append(f"<p>{_inline(b).replace(chr(10), '<br>')}</p>")
    return "\n".join(saida)


def _secao_noticias(noticias, por_pagina=5):
    if not noticias:
        return "Nenhuma notícia recente foi recuperada."
    lista = noticias_como_html(noticias)
    controles = (
        '<div class="paginacao">'
        '<button id="nt-ant" class="btn-pg" type="button">← Anterior</button>'
        '<span id="nt-pos" class="nt-pos"></span>'
        '<button id="nt-prox" class="btn-pg" type="button">Próxima →</button>'
        '</div>')
    js = (
        "<script>(function(){"
        f"var POR={por_pagina};"
        "var itens=[].slice.call(document.querySelectorAll('.nt-item'));"
        "var total=itens.length, paginas=Math.max(1, Math.ceil(total/POR)), pag=1;"
        "var ant=document.getElementById('nt-ant'), prox=document.getElementById('nt-prox');"
        "var pos=document.getElementById('nt-pos');"
        "function render(){"
        "itens.forEach(function(el,i){el.style.display=(i>=(pag-1)*POR&&i<pag*POR)?'':'none';});"
        "ant.disabled=(pag<=1); prox.disabled=(pag>=paginas);"
        "pos.textContent=pag+' / '+paginas;"
        "}"
        "ant.onclick=function(){if(pag>1){pag--;render();}};"
        "prox.onclick=function(){if(pag<paginas){pag++;render();}};"
        "render();"
        "})();</script>")
    return lista + controles + js


def _resolver_ref(min_d, max_d, data_ref):
    if not data_ref:
        return max_d, ""
    try:
        d = pd.Timestamp(data_ref).normalize()
    except Exception:
        return max_d, f"A data informada ('{data_ref}') é inválida. Exibindo o período mais recente."
    if d < min_d or d > max_d:
        aviso = (f"A data escolhida ({d.date()}) está fora do período disponível "
                 f"({min_d.date()} a {max_d.date()}). Exibindo o período mais recente.")
        return max_d, aviso
    return d, ""


def construir_conteudo(data_ref=None):
    aud = Auditor()
    aud.registrar("inicio_html", data_ref=data_ref)
    min_d, max_d = metrics.intervalo_datas()
    ref, aviso = _resolver_ref(min_d, max_d, data_ref)
    df = metrics.carregar_dados(desde=ref - pd.DateOffset(months=13))
    res = metrics.calcular_todas(df, ref=ref)
    aud.tool_resultado("consultar_metricas", f"{len(res.metricas)} métricas (ref={ref.date()})")
    graficos = charts.gerar_todos(df, ref)
    aud.tool_resultado("gerar_graficos", "5 gráficos em memória")
    try:
        noticias = ordenar_por_data(buscar_noticias())
    except Exception as e:
        noticias = []
        aud.erro("buscar_noticias", str(e))
    aud.tool_resultado("consultar_noticias", f"{len(noticias)} manchetes")

    corpus = [f"{n.titulo} ({n.fonte})" for n in noticias] + DICIONARIO_CAMPOS
    contexto = rag.montar_contexto(corpus, CONSULTA_RAG, k=4)
    aud.tool_resultado("rag_contexto", f"{len(corpus)} documentos indexados")

    comentario = _md_para_html(comentar_metricas(res, contexto, aud))
    ntxt = _secao_noticias(noticias)
    aviso_html = f'<div class="aviso">⚠ {aviso}</div>' if aviso else ""

    frag = f"""<div class="meta">Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} ·
Data de referência dos dados: {ref.date()} · Casos (últimos 12 meses): {res.total_casos}</div>
{aviso_html}
<h2>Métricas principais</h2>
<div class="cards">{_cards(res)}</div>

<h2>Evolução dos casos</h2>
<div class="grafico"><img src="{_img(graficos['diario'])}" alt="Casos diários"></div>
<div class="grafico"><img src="{_img(graficos['mensal'])}" alt="Casos mensais"></div>

<h2>Perfil dos casos</h2>
<div class="grafico"><img src="{_img(graficos['faixa_etaria'])}" alt="Casos e óbitos por faixa etária"></div>
<div class="grafico"><img src="{_img(graficos['tipo_virus'])}" alt="Casos por classificação final"></div>
<div class="grafico"><img src="{_img(graficos['geografico'])}" alt="Casos por estado"></div>

<h2>Análise do cenário</h2>
<div class="bloco">{comentario}</div>

<h2>Notícias recentes (contexto)</h2>
<div class="bloco">{ntxt}</div>"""
    aud.registrar("fim_html")
    return frag


def construir_pagina():
    min_d, max_d = metrics.intervalo_datas()
    latest = max_d.date().isoformat()
    return f"""<!doctype html>
<html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório de Vigilância — SRAG</title>
{_CSS}
</head><body>
<header>
<div class="cabecalho">
  <div class="titulo"><h1>Relatório de Vigilância — SRAG</h1></div>
  <div class="toolbar">
    <div class="picker"><label>Data de referência:</label>
      <input id="dt" type="date" value="{latest}" min="{min_d.date()}" max="{max_d.date()}"></div>
    <a id="btn-atualizar" class="btn" href="#">↻ Atualizar dados</a>
  </div>
</div>
</header>
<main id="conteudo"></main>
<footer>Indicium HealthCare — PoC · métricas oficiais do Open DATASUS (SIVEP-Gripe).
Notícias são fontes externas usadas como contexto.</footer>
<script>
function carregar(data, atualizar){{
  var alvo=document.getElementById("conteudo");
  alvo.innerHTML='<div class="carregando"><div class="spin"></div><p>Carregando o relatório…</p></div>';
  var q="?data="+encodeURIComponent(data)+(atualizar?"&atualizar=1":"");
  fetch("/conteudo"+q).then(function(r){{return r.text();}}).then(function(h){{
    alvo.innerHTML=h;
    alvo.querySelectorAll("script").forEach(function(o){{
      var s=document.createElement("script"); s.textContent=o.textContent; o.replaceWith(s);
    }});
  }}).catch(function(e){{ alvo.innerHTML="<p style='color:#b00'>Falha ao carregar: "+e+"</p>"; }});
}}
var dt=document.getElementById("dt");
dt.addEventListener("change", function(){{ carregar(dt.value, false); }});
document.getElementById("btn-atualizar").addEventListener("click", function(e){{
  e.preventDefault(); carregar(dt.value, true);
}});
carregar(dt.value, false);
</script>
</body></html>"""
