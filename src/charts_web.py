import json


def _canvas(cid, config, titulo):
    config.setdefault("options", {}).setdefault("plugins", {})["title"] = {"display": True, "text": titulo}
    config["options"]["responsive"] = True
    return (f'<div class="grafico"><canvas id="{cid}" height="120"></canvas></div>'
            f'<script>if(window.Chart){{new Chart(document.getElementById("{cid}"),'
            f'{json.dumps(config, ensure_ascii=False)});}}</script>')


def blocos_interativos(series):
    dia = series["diario"]
    diario = _canvas("g-diario", {"type": "bar", "data": {
        "labels": [d.strftime("%d/%m") for d in dia.index],
        "datasets": [{"label": "Casos", "data": [int(v) for v in dia.values], "backgroundColor": "#2c7fb8"}]}},
        "Casos diários (últimos 30 dias)")

    mes = series["mensal"]
    mensal = _canvas("g-mensal", {"type": "line", "data": {
        "labels": [p.strftime("%m/%Y") for p in mes.index],
        "datasets": [{"label": "Casos", "data": [int(v) for v in mes.values],
                      "borderColor": "#d95f0e", "backgroundColor": "#d95f0e", "fill": False, "tension": 0.2}]}},
        "Casos mensais (últimos 12 meses)")

    cf, of = series["faixa_casos"], series["faixa_obitos"]
    faixa = _canvas("g-faixa", {"type": "bar", "data": {
        "labels": list(cf.index),
        "datasets": [{"label": "Casos", "data": [int(v) for v in cf.values], "backgroundColor": "#2c7fb8"},
                     {"label": "Óbitos", "data": [int(v) for v in of.values], "backgroundColor": "#c0392b"}]}},
        "Casos e óbitos por faixa etária")

    vv = series["virus"]
    virus = _canvas("g-virus", {"type": "bar", "options": {"indexAxis": "y"}, "data": {
        "labels": [str(i) for i in vv.index],
        "datasets": [{"label": "Casos", "data": [int(v) for v in vv.values], "backgroundColor": "#4a8c3f"}]}},
        "Casos por classificação final")

    uu = series["uf"]
    uf = _canvas("g-uf", {"type": "bar", "options": {"indexAxis": "y"}, "data": {
        "labels": [str(i) for i in uu.index],
        "datasets": [{"label": "Casos", "data": [int(v) for v in uu.values], "backgroundColor": "#6a51a3"}]}},
        "Casos por estado (top UFs)")

    return {"diario": diario, "mensal": mensal, "faixa_etaria": faixa, "tipo_virus": virus, "geografico": uf}
