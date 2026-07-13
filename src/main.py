import argparse
from dotenv import load_dotenv

load_dotenv()


def main():
    p = argparse.ArgumentParser(description="Agente de relatório de SRAG")
    p.add_argument("--construir-banco", action="store_true")
    p.add_argument("--agente", metavar="PERGUNTA", default=None)
    a = p.parse_args()
    if a.construir_banco:
        from data_pipeline import executar_pipeline
        executar_pipeline()
        return
    if a.agente:
        from agent import construir_agente_react
        r = construir_agente_react().invoke({"messages": [("user", a.agente)]})
        print(r["messages"][-1].content)
        return
    from app import iniciar
    iniciar()


if __name__ == "__main__":
    main()
