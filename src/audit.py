import json
from datetime import datetime, timezone
from config import LOGS_DIR, AUDIT_MAX_BYTES


class Auditor:
    def __init__(self, arquivo="audit.jsonl", max_bytes=AUDIT_MAX_BYTES):
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.caminho = LOGS_DIR / arquivo
        self.max_bytes = max_bytes

    def _rotacionar_se_preciso(self):
        try:
            if self.caminho.exists() and self.caminho.stat().st_size >= self.max_bytes:
                carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
                self.caminho.rename(self.caminho.with_name(f"{self.caminho.stem}.{carimbo}.jsonl"))
        except OSError:
            pass

    def registrar(self, evento, **dados):
        self._rotacionar_se_preciso()
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
