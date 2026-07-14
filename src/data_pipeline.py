import os
import sqlite3
from pathlib import Path
import pandas as pd
from config import (RAW_CSV_PATH, RAW_CSV_DIR, RAW_CSV_GLOB, CHUNKSIZE, DB_PATH, TABLE_NAME,
                    COLUNAS_USADAS, COLUNAS_DATA, COLUNAS_SENSIVEIS_REMOVER, TP_IDADE_ANO,
                    EVOLUCAO_OBITOS, EVOLUCAO_DESFECHO_CONHECIDO, SIM, NAO,
                    FAIXAS_ETARIAS_LIMITES, FAIXAS_ETARIAS_ROTULOS,
                    AGG_DIARIO, AGG_FAIXA, AGG_UF, AGG_VIRUS)

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


def _bandeira(df, coluna, conjunto):
    if coluna in df.columns:
        return df[coluna].isin(conjunto).astype("int64")
    return pd.Series(0, index=df.index, dtype="int64")


def enriquecer(df):
    df["EH_OBITO"] = _bandeira(df, "EVOLUCAO", EVOLUCAO_OBITOS)
    df["EH_DESFECHO"] = _bandeira(df, "EVOLUCAO", EVOLUCAO_DESFECHO_CONHECIDO)
    df["UTI_SIM"] = _bandeira(df, "UTI", {SIM})
    df["UTI_CONHECIDO"] = _bandeira(df, "UTI", {SIM, NAO})
    df["VACCOV_SIM"] = _bandeira(df, "VACINA_COV", {SIM})
    df["VACCOV_CONHECIDO"] = _bandeira(df, "VACINA_COV", {SIM, NAO})
    df["VACGRIPE_SIM"] = _bandeira(df, "VACINA", {SIM})
    df["VACGRIPE_CONHECIDO"] = _bandeira(df, "VACINA", {SIM, NAO})
    idade = pd.to_numeric(df["IDADE_ANOS"], errors="coerce") if "IDADE_ANOS" in df.columns else pd.Series(index=df.index, dtype="float64")
    faixa = pd.cut(idade, bins=FAIXAS_ETARIAS_LIMITES, labels=FAIXAS_ETARIAS_ROTULOS, right=False)
    df["FAIXA"] = faixa.astype("object").where(faixa.notna(), None)
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
    df = enriquecer(df)
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


def construir_agregados(conn):
    cur = conn.cursor()
    cur.executescript(f"""
    DROP TABLE IF EXISTS {AGG_DIARIO};
    CREATE TABLE {AGG_DIARIO} AS
      SELECT DATA_CASO,
             COUNT(*) casos,
             SUM(EH_OBITO) obitos,
             SUM(EH_DESFECHO) desfecho,
             SUM(UTI_SIM) uti_sim,
             SUM(UTI_CONHECIDO) uti_conhecido,
             SUM(VACCOV_SIM) vaccov_sim,
             SUM(VACCOV_CONHECIDO) vaccov_conhecido,
             SUM(VACGRIPE_SIM) vacgripe_sim,
             SUM(VACGRIPE_CONHECIDO) vacgripe_conhecido
      FROM {TABLE_NAME} GROUP BY DATA_CASO;
    DROP TABLE IF EXISTS {AGG_FAIXA};
    CREATE TABLE {AGG_FAIXA} AS
      SELECT DATA_CASO, FAIXA, COUNT(*) casos, SUM(EH_OBITO) obitos
      FROM {TABLE_NAME} GROUP BY DATA_CASO, FAIXA;
    DROP TABLE IF EXISTS {AGG_UF};
    CREATE TABLE {AGG_UF} AS
      SELECT DATA_CASO, SG_UF_NOT uf, COUNT(*) casos
      FROM {TABLE_NAME} WHERE SG_UF_NOT IS NOT NULL GROUP BY DATA_CASO, SG_UF_NOT;
    DROP TABLE IF EXISTS {AGG_VIRUS};
    CREATE TABLE {AGG_VIRUS} AS
      SELECT DATA_CASO, CLASSI_FIN classi, COUNT(*) casos
      FROM {TABLE_NAME} GROUP BY DATA_CASO, CLASSI_FIN;
    CREATE INDEX IF NOT EXISTS idx_agg_diario ON {AGG_DIARIO} (DATA_CASO);
    CREATE INDEX IF NOT EXISTS idx_agg_faixa ON {AGG_FAIXA} (DATA_CASO);
    CREATE INDEX IF NOT EXISTS idx_agg_uf ON {AGG_UF} (DATA_CASO);
    CREATE INDEX IF NOT EXISTS idx_agg_virus ON {AGG_VIRUS} (DATA_CASO);
    """)
    conn.commit()


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
    with sqlite3.connect(DB_PATH) as conn:
        construir_agregados(conn)
    print(f"[pipeline] {len(caminhos)} arquivo(s) processado(s), {total} registros no banco (+ agregados)")
    return total


if __name__ == "__main__":
    executar_pipeline()
