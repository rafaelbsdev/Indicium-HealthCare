import json
import shutil
from pathlib import Path
from urllib.request import urlopen, Request
import data_pipeline
from config import RECURSOS_VIVOS, CKAN_RESOURCE_API, RAW_CSV_DIR


def resolver_url(resource_id, abrir=urlopen):
    req = Request(f"{CKAN_RESOURCE_API}?id={resource_id}", headers={"User-Agent": "srag-agent"})
    with abrir(req) as resp:
        dados = json.loads(resp.read().decode("utf-8"))
    return dados["result"]["url"]


def baixar_arquivo(url, destino, abrir=urlopen):
    destino = Path(destino)
    parcial = destino.with_suffix(destino.suffix + ".part")
    req = Request(url, headers={"User-Agent": "srag-agent"})
    with abrir(req) as resp, open(parcial, "wb") as saida:
        shutil.copyfileobj(resp, saida)
    parcial.replace(destino)
    return destino


def atualizar(recursos=None, pasta=None, resolver=resolver_url, baixar=baixar_arquivo):
    recursos = recursos if recursos is not None else RECURSOS_VIVOS
    pasta = Path(pasta or RAW_CSV_DIR)
    pasta.mkdir(parents=True, exist_ok=True)
    baixados = []
    for ano, resource_id in recursos.items():
        for antigo in pasta.glob(f"INFLUD{ano}*.csv"):
            antigo.unlink()
        destino = pasta / f"INFLUD{ano}-vivo.csv"
        baixar(resolver(resource_id), destino)
        baixados.append(destino)
    total = data_pipeline.executar_pipeline()
    return {"arquivos": [str(b) for b in baixados], "registros": total}
