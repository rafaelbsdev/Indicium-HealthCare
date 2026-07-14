import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"
DB_PATH = Path(os.environ.get("SRAG_DB_PATH", DATA_DIR / "srag.db"))
RAW_CSV_PATH = DATA_DIR / "INFLUD19-23-03-2026.csv"
RAW_CSV_DIR = DATA_DIR
RAW_CSV_GLOB = "INFLUD*.csv"
CHUNKSIZE = 100000
TABLE_NAME = "srag"
AGG_DIARIO = "agg_diario"
AGG_FAIXA = "agg_faixa"
AGG_UF = "agg_uf"
AGG_VIRUS = "agg_virus"
META_TABLE = "meta"
AUDIT_MAX_BYTES = 5_000_000
CKAN_RESOURCE_API = "https://dadosabertos.saude.gov.br/api/3/action/resource_show"
RECURSOS_VIVOS = {"25": "20c49de3-ddc3-4b76-a942-1518eaae9c91",
                  "26": "74091efc-3f75-42e8-a6fa-6b79a8d30582"}
COLUNAS_USADAS = ["DT_SIN_PRI","DT_NOTIFIC","DT_INTERNA","DT_ENTUTI","DT_SAIDUTI","DT_EVOLUCA","EVOLUCAO","UTI","VACINA","VACINA_COV","HOSPITAL","CLASSI_FIN","SG_UF_NOT","CS_SEXO","NU_IDADE_N","TP_IDADE","DT_NASC"]
COLUNAS_DATA = ["DT_SIN_PRI","DT_NOTIFIC","DT_INTERNA","DT_ENTUTI","DT_SAIDUTI","DT_EVOLUCA"]
COLUNAS_SENSIVEIS_REMOVER = ["PAC_COCBO","PAC_DSCBO"]
TP_IDADE_ANO = "3"
EVOLUCAO_OBITOS = {"2","3"}
EVOLUCAO_DESFECHO_CONHECIDO = {"1","2","3"}
CLASSI_FIN_NOMES = {"1":"Influenza","2":"Outro vírus respiratório","3":"Outro agente etiológico","4":"Não especificado","5":"COVID-19"}
FAIXAS_ETARIAS_LIMITES = [0,10,20,30,40,50,60,70,80,200]
FAIXAS_ETARIAS_ROTULOS = ["0-9","10-19","20-29","30-39","40-49","50-59","60-69","70-79","80+"]
TOP_UF = 10
SIM = "1"; NAO = "2"; IGNORADO = "9"
DATA_REFERENCIA = None
JANELA_CURTA_DIAS = 30
JANELA_LONGA_MESES = 12
