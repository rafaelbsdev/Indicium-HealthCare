import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from config import (JANELA_CURTA_DIAS, JANELA_LONGA_MESES, FAIXAS_ETARIAS_LIMITES,
                    FAIXAS_ETARIAS_ROTULOS, CLASSI_FIN_NOMES, EVOLUCAO_OBITOS, TOP_UF)


def _fig_bytes(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    return buf.getvalue()


def _janela(df, ref, meses=JANELA_LONGA_MESES):
    inicio = ref - pd.DateOffset(months=meses)
    return df[(df["DATA_CASO"] > inicio) & (df["DATA_CASO"] <= ref)]


def _faixas(idades):
    return pd.cut(pd.to_numeric(idades, errors="coerce"), bins=FAIXAS_ETARIAS_LIMITES,
                  labels=FAIXAS_ETARIAS_ROTULOS, right=False)


def _num_compacto(v):
    v = int(v)
    if v >= 1000:
        return f"{v/1000:.1f}k".replace(".0k", "k")
    return str(v)


def grafico_casos_diarios(df, ref, janela_dias=JANELA_CURTA_DIAS):
    inicio = ref - pd.Timedelta(days=janela_dias)
    s = df[(df["DATA_CASO"] > inicio) & (df["DATA_CASO"] <= ref)].groupby("DATA_CASO").size()
    s = s.reindex(pd.date_range(inicio + pd.Timedelta(days=1), ref, freq="D"), fill_value=0)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(s.index, s.values, color="#2c7fb8")
    ax.set_title(f"Casos diários de SRAG — últimos {janela_dias} dias (até {ref.date()})", fontweight="bold")
    ax.set_xlabel("Data"); ax.set_ylabel("Nº de casos")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m")); fig.autofmt_xdate(rotation=45)
    ax.grid(axis="y", linestyle="--", alpha=0.4); fig.tight_layout()
    return _fig_bytes(fig)


def grafico_casos_mensais(df, ref, janela_meses=JANELA_LONGA_MESES):
    inicio = ref - pd.DateOffset(months=janela_meses)
    r = df[(df["DATA_CASO"] > inicio) & (df["DATA_CASO"] <= ref)].copy()
    r["MES"] = r["DATA_CASO"].dt.to_period("M")
    s = r.groupby("MES").size().reindex(
        pd.period_range((inicio + pd.Timedelta(days=1)).to_period("M"), ref.to_period("M"), freq="M"), fill_value=0)
    rot = [p.strftime("%m/%Y") for p in s.index]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(rot, s.values, marker="o", color="#d95f0e", linewidth=2)
    ax.fill_between(rot, s.values, alpha=0.15, color="#d95f0e")
    ax.set_title(f"Casos mensais de SRAG — últimos {janela_meses} meses (até {ref.date()})", fontweight="bold")
    ax.set_xlabel("Mês"); ax.set_ylabel("Nº de casos")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    ax.grid(axis="y", linestyle="--", alpha=0.4); fig.tight_layout()
    return _fig_bytes(fig)


def grafico_faixa_etaria(df, ref, janela_meses=JANELA_LONGA_MESES):
    r = _janela(df, ref, janela_meses)
    casos = _faixas(r.get("IDADE_ANOS")).value_counts().reindex(FAIXAS_ETARIAS_ROTULOS, fill_value=0)
    obitos_df = r[r["EVOLUCAO"].isin(EVOLUCAO_OBITOS)] if "EVOLUCAO" in r.columns else r.iloc[0:0]
    obitos = _faixas(obitos_df.get("IDADE_ANOS")).value_counts().reindex(FAIXAS_ETARIAS_ROTULOS, fill_value=0)
    x = np.arange(len(FAIXAS_ETARIAS_ROTULOS)); larg = 0.42
    fig, ax = plt.subplots(figsize=(10, 4.8))
    b1 = ax.bar(x - larg/2, casos.values, larg, label="Casos", color="#2c7fb8")
    b2 = ax.bar(x + larg/2, obitos.values, larg, label="Óbitos", color="#c0392b")
    ax.bar_label(b1, labels=[_num_compacto(v) for v in casos.values], fontsize=7, rotation=90, padding=3)
    ax.bar_label(b2, labels=[_num_compacto(v) for v in obitos.values], fontsize=7, rotation=90, padding=3)
    topo = max([int(v) for v in casos.values] + [int(v) for v in obitos.values] + [1])
    ax.set_ylim(top=topo * 1.18)
    ax.set_title(f"Casos e óbitos por faixa etária — últimos {janela_meses} meses (até {ref.date()})", fontweight="bold")
    ax.set_xlabel("Faixa etária (anos)"); ax.set_ylabel("Nº de pessoas")
    ax.set_xticks(x); ax.set_xticklabels(FAIXAS_ETARIAS_ROTULOS)
    ax.legend(); ax.grid(axis="y", linestyle="--", alpha=0.4); fig.tight_layout()
    return _fig_bytes(fig)


def grafico_tipo_virus(df, ref, janela_meses=JANELA_LONGA_MESES):
    r = _janela(df, ref, janela_meses)
    serie = r["CLASSI_FIN"].map(CLASSI_FIN_NOMES).fillna("Não informado")
    cont = serie.value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.barh(cont.index.astype(str), cont.values, color="#4a8c3f")
    ax.set_title(f"Casos por classificação final — últimos {janela_meses} meses (até {ref.date()})", fontweight="bold")
    ax.set_xlabel("Nº de casos"); ax.set_ylabel("Classificação")
    for i, v in enumerate(cont.values):
        ax.text(v, i, f" {int(v)}", va="center", fontsize=9)
    ax.grid(axis="x", linestyle="--", alpha=0.4); fig.tight_layout()
    return _fig_bytes(fig)


def grafico_geografico(df, ref, janela_meses=JANELA_LONGA_MESES, top=TOP_UF):
    r = _janela(df, ref, janela_meses)
    cont = r["SG_UF_NOT"].dropna().value_counts().head(top).sort_values()
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.barh(cont.index.astype(str), cont.values, color="#6a51a3")
    ax.set_title(f"Casos por estado (top {top}) — últimos {janela_meses} meses (até {ref.date()})", fontweight="bold")
    ax.set_xlabel("Nº de casos"); ax.set_ylabel("UF de notificação")
    for i, v in enumerate(cont.values):
        ax.text(v, i, f" {int(v)}", va="center", fontsize=9)
    ax.grid(axis="x", linestyle="--", alpha=0.4); fig.tight_layout()
    return _fig_bytes(fig)


def gerar_todos(df, ref):
    return {"diario": grafico_casos_diarios(df, ref),
            "mensal": grafico_casos_mensais(df, ref),
            "faixa_etaria": grafico_faixa_etaria(df, ref),
            "tipo_virus": grafico_tipo_virus(df, ref),
            "geografico": grafico_geografico(df, ref)}
