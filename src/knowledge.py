DICIONARIO_CAMPOS = [
    "EVOLUCAO: evolução do caso. 1 = cura, 2 = óbito, 3 = óbito por outras causas, 9 = ignorado.",
    "UTI: internação em unidade de terapia intensiva (UTI). 1 = sim, 2 = não, 9 = ignorado.",
    "VACINA: vacina contra gripe (influenza). 1 = sim, 2 = não, 9 = ignorado.",
    "VACINA_COV: vacina contra COVID-19. 1 = sim, 2 = não, 9 = ignorado.",
    "CLASSI_FIN: classificação final do caso. 1 = influenza, 2 = outro vírus respiratório, "
    "3 = outro agente etiológico, 4 = SRAG não especificado, 5 = SRAG por COVID-19.",
    "DT_SIN_PRI: data dos primeiros sintomas; base da série temporal de casos.",
    "DT_INTERNA: data de internação hospitalar.",
    "HOSPITAL: houve internação hospitalar. 1 = sim, 2 = não, 9 = ignorado.",
    "SG_UF_NOT: unidade federativa (estado) de notificação do caso.",
]


FONTES_OFICIAIS = [
    "InfoGripe (Fiocruz): boletim semanal que monitora a tendência de casos de SRAG "
    "por região e faixa etária, sinalizando alta, queda ou estabilidade.",
    "Boletins epidemiológicos do Ministério da Saúde: acompanham covid-19, influenza "
    "e outros vírus respiratórios de importância em saúde pública, com dados de SRAG.",
    "SIVEP-Gripe: sistema oficial de notificação de casos e óbitos por SRAG no Brasil, "
    "base dos dados deste relatório.",
]
