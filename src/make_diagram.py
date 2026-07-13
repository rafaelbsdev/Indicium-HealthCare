from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


def _caixa(ax, x, y, w, h, t, cor):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                linewidth=1.5, edgecolor="#333", facecolor=cor))
    ax.text(x+w/2, y+h/2, t, ha="center", va="center", fontsize=9.5, fontweight="bold")


def _seta(ax, p1, p2, t=""):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=14, linewidth=1.3, color="#555"))
    if t:
        ax.text((p1[0]+p2[0])/2, (p1[1]+p2[1])/2+0.12, t, ha="center", fontsize=7.5, style="italic", color="#444")


def gerar():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 7.5)); ax.set_xlim(0, 12); ax.set_ylim(0, 10); ax.axis("off")
    ax.text(6, 9.6, "Arquitetura — Agente de Relatório de SRAG", ha="center", fontsize=14, fontweight="bold")
    _caixa(ax, 0.4, 8.0, 2.2, 0.9, "Usuário\n(profissional de saúde)", "#e8e8e8")
    _caixa(ax, 4.6, 7.6, 2.8, 1.3, "AGENTE ORQUESTRADOR\n(LangGraph — ReAct)", "#cfe8f9")
    _caixa(ax, 9.2, 7.7, 2.4, 1.1, "LLM\nClaude (Anthropic)", "#fde3cf")
    _caixa(ax, 4.4, 5.9, 3.2, 0.8, "Guardrails\n(escopo · anti-alucinação · LGPD)", "#e5f5e0")
    _caixa(ax, 8.6, 5.9, 3.0, 0.8, "Auditoria\n(log JSONL de decisões)", "#f2e5f9")
    _caixa(ax, 0.4, 3.6, 3.0, 1.0, "Tool: Métricas\n(consulta o banco)", "#dbeeff")
    _caixa(ax, 4.5, 3.6, 3.0, 1.0, "Tool: Gráficos\n(5: tempo, idade, vírus, UF)", "#dbeeff")
    _caixa(ax, 8.6, 3.6, 3.0, 1.0, "Tool: Notícias\n(RSS + RAG vetorial\n(Chroma + embeddings))", "#dbeeff")
    _caixa(ax, 0.4, 1.4, 3.0, 1.0, "Banco SQLite\n(CSV DATASUS tratado)", "#fff2cc")
    _caixa(ax, 4.5, 1.4, 3.0, 1.0, "Servidor web local\n(localhost:8000)", "#fff2cc")
    _caixa(ax, 8.6, 1.4, 3.0, 1.0, "Fontes de notícias\n(Google Notícias)", "#fff2cc")
    _seta(ax, (2.6, 8.45), (4.6, 8.25), "pergunta"); _seta(ax, (7.4, 8.25), (9.2, 8.25), "raciocínio")
    _seta(ax, (9.2, 7.9), (7.4, 8.0), "resposta"); _seta(ax, (6.0, 7.6), (6.0, 6.7)); _seta(ax, (7.4, 7.9), (9.6, 6.7))
    _seta(ax, (5.4, 7.6), (1.9, 4.6), "chama"); _seta(ax, (6.0, 7.6), (6.0, 4.6), "chama"); _seta(ax, (6.6, 7.6), (10.1, 4.6), "chama")
    _seta(ax, (1.9, 3.6), (1.9, 2.4)); _seta(ax, (6.0, 3.6), (6.0, 2.4)); _seta(ax, (10.1, 3.6), (10.1, 2.4))
    fig.tight_layout(); p = DOCS_DIR / "arquitetura.pdf"
    fig.savefig(p, format="pdf", bbox_inches="tight"); fig.savefig(DOCS_DIR / "arquitetura.png", dpi=130, bbox_inches="tight")
    plt.close(fig); return p


if __name__ == "__main__":
    print("Diagrama:", gerar())
