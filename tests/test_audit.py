import json
from audit import Auditor

def test_grava_linha_json(pastas_temporarias):
    a = Auditor(); a.registrar("teste", detalhe="ok", numero=42)
    obj = json.loads(a.caminho.read_text(encoding="utf-8").strip())
    assert obj["evento"] == "teste" and obj["numero"] == 42 and "timestamp" in obj

def test_acumula_eventos(pastas_temporarias):
    a = Auditor()
    a.tool_chamada("t", {"x": 1}); a.guardrail("g", True); a.erro("c", "x")
    linhas = a.caminho.read_text(encoding="utf-8").strip().splitlines()
    assert [json.loads(l)["evento"] for l in linhas] == ["tool_call","guardrail","error"]

def test_guardrail_reprovado(pastas_temporarias):
    a = Auditor(); a.guardrail("r", aprovado=False, motivo="falhou")
    obj = json.loads(a.caminho.read_text(encoding="utf-8").strip())
    assert obj["aprovado"] is False and obj["motivo"] == "falhou"


def test_auditoria_rotaciona_por_tamanho(pastas_temporarias):
    import audit
    a = audit.Auditor(max_bytes=10)
    a.registrar("e1", x=1)
    a.registrar("e2", x=2)
    logs = pastas_temporarias["logs"]
    assert len(list(logs.glob("audit.*.jsonl"))) >= 1          # gerou arquivo rotacionado
    assert (logs / "audit.jsonl").read_text(encoding="utf-8").count("\n") == 1
