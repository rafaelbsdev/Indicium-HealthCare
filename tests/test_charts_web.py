import agregados, charts_web


def test_blocos_interativos_tem_canvas(db_temporario):
    b = charts_web.blocos_interativos(agregados.series_graficos())
    assert set(b) == {"diario", "mensal", "faixa_etaria", "tipo_virus", "geografico"}
    assert all("<canvas" in v and "new Chart(" in v for v in b.values())
