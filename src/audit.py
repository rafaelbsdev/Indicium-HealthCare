import json
from datetime import datetime, timezone
from config import LOGS_DIR


class Auditor:
    def __init__(self, arquivo="audit.jsonl"):
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.caminho = LOGS_DIR / arquivo

    def registrar(self, evento, **dados):
        linha = {"timestamp": datetime.now(timezone.utc).isoformat(), "evento": evento, **dados}
        with open(self.caminho, "a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")

    def tool_chamada(self, nome, argumentos):
        self.registrar("tool_call", tool=nome, argumentos=argumentos)

    def tool_resultado(self, nome, resumo):
        self.registrar("tool_result", tool=nome, resumo=resumo)

    def guardrail(self, nome, aprovado, motivo=""):
        self.registrar("guardrail", regra=nome, aprovado=aprovado, motivo=motivo)

    def decisao_llm(self, resumo):
        self.registrar("llm_decision", resumo=resumo)

    def erro(self, contexto, mensagem):
        self.registrar("error", contexto=contexto, mensagem=mensagem)
