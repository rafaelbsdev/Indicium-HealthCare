import re
from dataclasses import dataclass


@dataclass
class ResultadoGuardrail:
    aprovado: bool
    motivo: str = ""


TERMOS_NO_ESCOPO = ["srag","síndrome respiratória","sindrome respiratoria","gripe",
    "influenza","covid","surto","internação","internacao","uti","óbito","obito",
    "mortalidade","vacina","caso","relatório","relatorio","saúde","saude","epidem"]


def validar_escopo(pergunta):
    p = pergunta.lower()
    if any(t in p for t in TERMOS_NO_ESCOPO):
        return ResultadoGuardrail(True)
    return ResultadoGuardrail(False,
        "Pergunta fora do escopo: este agente só trata de SRAG e saúde pública.")


def validar_numeros_do_texto(texto, valores_permitidos, tolerancia=0.1):
    for bruto in re.findall(r"(\d+[.,]?\d*)\s*%", texto):
        valor = float(bruto.replace(",", "."))
        if not any(abs(abs(valor) - abs(v)) <= tolerancia for v in valores_permitidos):
            return ResultadoGuardrail(False,
                f"A análise citou {bruto}% que não confere com nenhuma das métricas "
                f"oficiais calculadas.")
    return ResultadoGuardrail(True)


PADRAO_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
PADRAO_NOME = re.compile(r"\bpaciente\s+[A-ZÁÉÍÓÚ][a-záéíóú]+\s+[A-ZÁÉÍÓÚ]", re.UNICODE)


def validar_sem_dado_sensivel(texto):
    if PADRAO_CPF.search(texto):
        return ResultadoGuardrail(False, "Saída contém algo com formato de CPF.")
    if PADRAO_NOME.search(texto):
        return ResultadoGuardrail(False, "Saída parece citar nome de paciente.")
    return ResultadoGuardrail(True)


def sanitizar_saida(texto):
    return PADRAO_CPF.sub("[dado removido]", texto)
