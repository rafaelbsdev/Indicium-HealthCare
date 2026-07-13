import os
import sqlite3
from pathlib import Path
import pandas as pd
from config import (RAW_CSV_PATH, RAW_CSV_DIR, RAW_CSV_GLOB, CHUNKSIZE, DB_PATH, TABLE_NAME,
                    COLUNAS_USADAS, COLUNAS_DATA, COLUNAS_SENSIVEIS_REMOVER, TP_IDADE_ANO)

_COLS = set(COLUNAS_USADAS)


def _colunas_presentes(caminho):
    cabecalho = pd.read_csv(caminho, sep=";", nrows=0)
    return [c for c in COLUNAS_USADAS if c in cabecalho.columns]


def listar_csvs(pasta=None, padrao=None):
    pasta = Path(pasta or RAW_CSV_DIR); padrao = padrao or RAW_CSV_GLOB
    achados = sorted(pasta.glob(padrao))
    if achados:
        return achados
    return [Path(RAW_CSV_PATH)] if Path(RAW_CSV_PATH).exists() else []


def carregar_csv(caminho):
    return pd.read_csv(caminho, sep=";", dtype=str, usecols=_colunas_presentes(caminho),
                       keep_default_na=True)


def ler_em_blocos(caminho, tamanho=None):
    return pd.read_csv(caminho, sep=";", dtype=str, usecols=_colunas_presentes(caminho),
                       keep_default_na=True, chunksize=tamanho or CHUNKSIZE)


def anonimizar(df):
    if "DT_NASC" in df.columns:
        nasc = pd.to_datetime(df["DT_NASC"], errors="coerce", utc=True).dt.tz_localize(None)
        df["ANO_NASC"] = nasc.dt.year.astype("Int64")
        df = df.drop(columns=["DT_NASC"])
    remover = [c for c in COLUNAS_SENSIVEIS_REMOVER if c in df.columns]
    if remover:
        df = df.drop(columns=remover)
    return df


def derivar_idade(df):
    if "NU_IDADE_N" in df.columns:
        idade = pd.to_numeric(df["NU_IDADE_N"], errors="coerce")
        if "TP_IDADE" in df.columns:
            tp = df["TP_IDADE"].astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
            idade = idade.where(tp == TP_IDADE_ANO, other=0)
        df["IDADE_ANOS"] = idade.astype("Int64")
    return df


def limpar(df):
    for col in COLUNAS_DATA:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True).dt.tz_localize(None)
    li = pd.Timestamp("2009-01-01")
    ls = pd.Timestamp.today().normalize()
    for col in COLUNAS_DATA:
        if col in df.columns:
            df.loc[(df[col] < li) | (df[col] > ls), col] = pd.NaT
    df = df.dropna(subset=["DT_SIN_PRI"]).copy()
    for col in ["EVOLUCAO","UTI","VACINA","VACINA_COV","HOSPITAL","CLASSI_FIN","SG_UF_NOT","CS_SEXO"]:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
            df[col] = df[col].replace({"": None, "nan": None})
    df = derivar_idade(df)
    df = anonimizar(df)
    df["DATA_CASO"] = df["DT_SIN_PRI"].dt.normalize()
    return df


def salvar_sqlite(df, substituir=True):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql(TABLE_NAME, conn, if_exists="replace" if substituir else "append", index=False)
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_data_caso ON {TABLE_NAME} (DATA_CASO)")


def _liberar_cache_do_disco(caminho):
    if hasattr(os, "posix_fadvise"):
        try:
            fd = os.open(str(caminho), os.O_RDONLY)
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
            os.close(fd)
        except OSError:
            pass


def executar_pipeline(caminhos=None, substituir=True):
    caminhos = caminhos if caminhos is not None else listar_csvs()
    total = 0
    primeiro = substituir
    for caminho in caminhos:
        for bloco in ler_em_blocos(caminho):
            limpo = limpar(bloco)
            if len(limpo) == 0:
                continue
            salvar_sqlite(limpo, substituir=primeiro)
            primeiro = False
            total += len(limpo)
        _liberar_cache_do_disco(caminho)
        print(f"[pipeline] {Path(caminho).name}: acumulado {total} registros")
    print(f"[pipeline] {len(caminhos)} arquivo(s) processado(s), {total} registros no banco")
    return total


if __name__ == "__main__":
    executar_pipeline()
