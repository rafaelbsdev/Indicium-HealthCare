import guardrails as gr


def test_escopo_aceita_srag():
    assert gr.validar_escopo("Gere o relatório de SRAG").aprovado is True


def test_escopo_recusa_fora_do_tema():
    r = gr.validar_escopo("receita de bolo de cenoura")
    assert r.aprovado is False and r.motivo


def test_numero_real_aprovado():
    assert gr.validar_numeros_do_texto("mortalidade de 12.15%", {12.15}).aprovado is True


def test_numero_inventado_reprovado_e_nomeado():
    r = gr.validar_numeros_do_texto("subiu para 87.4%", {12.15})
    assert r.aprovado is False
    assert "87.4" in r.motivo                 # o número é nomeado
    assert "não confere" in r.motivo.lower()  # linguagem honesta, sem afirmar erro


def test_numero_com_virgula():
    assert gr.validar_numeros_do_texto("12,15%", {12.15}).aprovado is True


def test_bloqueia_cpf():
    assert gr.validar_sem_dado_sensivel("CPF 123.456.789-00").aprovado is False


def test_texto_agregado_ok():
    assert gr.validar_sem_dado_sensivel("taxa geral de 12%").aprovado is True


def test_sanitizar_mascara_cpf():
    out = gr.sanitizar_saida("CPF 123.456.789-00 aqui")
    assert "123.456.789-00" not in out and "[dado removido]" in out


def test_numero_negativo_reconhecido_por_magnitude():
    # métrica -10.6 (queda); a análise cita "10,60%" sem o sinal -> deve passar
    assert gr.validar_numeros_do_texto("houve queda de 10,60%", {-10.6}).aprovado is True
