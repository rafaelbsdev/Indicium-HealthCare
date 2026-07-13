import rag


class EmbedderFake:
    VOCAB = ["mortalidade", "obitos", "uti", "vacinacao", "casos", "gripe"]

    def embed(self, textos):
        vetores = []
        for t in textos:
            tl = t.lower()
            vetores.append([float(tl.count(termo)) for termo in self.VOCAB])
        return vetores


def test_dividir_em_chunks_texto_longo():
    texto = " ".join([f"palavra{i}" for i in range(700)])
    chunks = rag.dividir_em_chunks(texto, tamanho=300, sobreposicao=50)
    assert len(chunks) >= 2
    assert all(len(c.split()) <= 300 for c in chunks)


def test_dividir_em_chunks_texto_curto():
    assert rag.dividir_em_chunks("uma manchete curta", tamanho=300) == ["uma manchete curta"]


def test_indice_memoria_retorna_mais_similar():
    emb = EmbedderFake()
    idx = rag.IndiceMemoria()
    docs = ["obitos e mortalidade subiram", "vacinacao avanca no pais"]
    idx.adicionar(docs, emb.embed(docs))
    achados = idx.buscar(emb.embed(["mortalidade"])[0], k=1)
    assert achados == ["obitos e mortalidade subiram"]


def test_rag_contexto_recupera_relevante():
    r = rag.RagContexto(embedder=EmbedderFake())
    r.indexar(["casos de uti aumentaram muito",
               "campanha de vacinacao contra gripe",
               "mortalidade por obitos em queda"])
    achados = r.recuperar("vacinacao", k=1)
    assert "vacinacao" in achados[0]


def test_rag_contexto_como_texto():
    r = rag.RagContexto(embedder=EmbedderFake())
    r.indexar(["mortalidade em alta"])
    texto = r.recuperar_como_texto("mortalidade", k=1)
    assert "mortalidade em alta" in texto


def test_rag_indexa_noticias_e_dicionario():
    from knowledge import DICIONARIO_CAMPOS
    r = rag.RagContexto(embedder=EmbedderFake())
    r.indexar(["surto de gripe preocupa"] + DICIONARIO_CAMPOS)
    achados = r.recuperar("uti", k=2)
    assert any("uti" in a.lower() for a in achados)


def test_montar_contexto_com_embedder_fake():
    ctx = rag.montar_contexto(
        ["casos de uti", "campanha de vacinacao", "mortalidade em queda"],
        "vacinacao", k=1, embedder=EmbedderFake())
    assert "vacinacao" in ctx


def test_montar_contexto_fallback_sem_embedder(monkeypatch):
    monkeypatch.setattr(rag, "criar_embedder_padrao", lambda: None)
    ctx = rag.montar_contexto(["item a", "item b"], "qualquer")
    assert "item a" in ctx and "item b" in ctx


def test_montar_contexto_fallback_vazio(monkeypatch):
    monkeypatch.setattr(rag, "criar_embedder_padrao", lambda: None)
    assert rag.montar_contexto([], "x") == "Sem contexto disponível."
