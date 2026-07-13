import make_diagram


def test_gerar_cria_pdf_e_png(tmp_path, monkeypatch):
    monkeypatch.setattr(make_diagram, "DOCS_DIR", tmp_path)
    p = make_diagram.gerar()
    assert p.exists() and p.stat().st_size > 0
    assert p.suffix == ".pdf"
    assert (tmp_path / "arquitetura.png").exists()
