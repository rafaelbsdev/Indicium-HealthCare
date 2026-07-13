import math


def dividir_em_chunks(texto, tamanho=300, sobreposicao=50):
    palavras = texto.split()
    if len(palavras) <= tamanho:
        return [texto]
    chunks = []
    passo = max(1, tamanho - sobreposicao)
    i = 0
    while i < len(palavras):
        chunks.append(" ".join(palavras[i:i + tamanho]))
        i += passo
    return chunks


def _cosseno(a, b):
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    return num / (da * db) if da and db else 0.0


class IndiceMemoria:
    def __init__(self):
        self.docs = []
        self.vetores = []

    def adicionar(self, docs, vetores):
        self.docs.extend(docs)
        self.vetores.extend(vetores)

    def buscar(self, vetor, k=3):
        ranqueados = sorted(
            zip(self.vetores, self.docs),
            key=lambda par: _cosseno(vetor, par[0]),
            reverse=True,
        )
        return [doc for _, doc in ranqueados[:k]]


class IndiceChroma:
    def __init__(self, colecao="srag_rag", persist_dir=None):
        import chromadb
        cliente = chromadb.PersistentClient(path=persist_dir) if persist_dir else chromadb.Client()
        self.colecao = cliente.get_or_create_collection(colecao)
        self._n = 0

    def adicionar(self, docs, vetores):
        ids = [str(self._n + i) for i in range(len(docs))]
        self.colecao.add(ids=ids, documents=docs, embeddings=vetores)
        self._n += len(docs)

    def buscar(self, vetor, k=3):
        r = self.colecao.query(query_embeddings=[vetor], n_results=k)
        return r["documents"][0]


class EmbedderLocal:
    def __init__(self, modelo="all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(modelo)

    def embed(self, textos):
        return self.model.encode(list(textos)).tolist()


class RagContexto:
    def __init__(self, embedder, indice=None):
        self.embedder = embedder
        self.indice = indice or IndiceMemoria()

    def indexar(self, textos):
        chunks = []
        for t in textos:
            chunks.extend(dividir_em_chunks(t))
        if chunks:
            self.indice.adicionar(chunks, self.embedder.embed(chunks))

    def recuperar(self, consulta, k=3):
        vetor = self.embedder.embed([consulta])[0]
        return self.indice.buscar(vetor, k)

    def recuperar_como_texto(self, consulta, k=3):
        return "\n".join(f"- {d}" for d in self.recuperar(consulta, k))


def criar_embedder_padrao():
    try:
        return EmbedderLocal()
    except Exception:
        return None


def montar_contexto(textos, consulta, k=4, embedder=None):
    if embedder is None:
        embedder = criar_embedder_padrao()
    if embedder is None:
        if not textos:
            return "Sem contexto disponível."
        return "\n".join(f"- {t}" for t in textos)
    r = RagContexto(embedder)
    r.indexar(textos)
    return r.recuperar_como_texto(consulta, k)
