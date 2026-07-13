import charts

PNG = b"\x89PNG\r\n\x1a\n"


def test_diario_retorna_png_bytes(df_limpo, ref):
    b = charts.grafico_casos_diarios(df_limpo, ref)
    assert isinstance(b, bytes) and b[:8] == PNG


def test_mensal_retorna_png_bytes(df_limpo, ref):
    b = charts.grafico_casos_mensais(df_limpo, ref)
    assert isinstance(b, bytes) and len(b) > 0


def test_faixa_etaria_retorna_png(df_limpo, ref):
    b = charts.grafico_faixa_etaria(df_limpo, ref)
    assert isinstance(b, bytes) and b[:8] == PNG


def test_tipo_virus_retorna_png(df_limpo, ref):
    b = charts.grafico_tipo_virus(df_limpo, ref)
    assert isinstance(b, bytes) and b[:8] == PNG


def test_geografico_retorna_png(df_limpo, ref):
    b = charts.grafico_geografico(df_limpo, ref)
    assert isinstance(b, bytes) and b[:8] == PNG


def test_gerar_todos_bytes(df_limpo, ref):
    c = charts.gerar_todos(df_limpo, ref)
    assert set(c) == {"diario", "mensal", "faixa_etaria", "tipo_virus", "geografico"}
    assert all(isinstance(v, bytes) for v in c.values())
