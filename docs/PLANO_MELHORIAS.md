# Plano de Melhorias — Sistema de Relatório de SRAG

Este documento mapeia **todas** as melhorias acordadas (exceto Docker, retirado a
pedido), na ordem recomendada de execução, com as necessidades, arquivos afetados,
dependências, testes e riscos de cada uma. Serve como roteiro de implementação.

## Princípios (valem para tudo)

- **TDD**: cada mudança começa por um teste que falha (red → green → refactor).
- **Código limpo**: sem comentários/docstrings no código; toda explicação vai para
  `docs/DOCUMENTACAO.md`. Este plano é atualizado conforme cada item é concluído.
- **Suíte sempre verde**: nenhuma fase encerra com teste vermelho (hoje: 123 testes).
- **Sem segredos versionados**: `.env`, CSVs e `*.db` continuam no `.gitignore`.
- **Compatibilidade**: nenhuma métrica oficial muda de valor sem um teste de
  paridade provando que o resultado é o mesmo de antes.

> **Atenção (item 1 concluído):** o esquema do banco mudou — agora inclui as tabelas
> `agg_*`. Bancos criados antes precisam ser **reconstruídos** com
> `python src/main.py --construir-banco`. Medição real: janela de 2021 caiu de
> ~3,7 GB / 19 s para ~124 MB / 1,5 s, com paridade de métricas comprovada por teste.

## Escala usada

- **Complexidade**: S (pequena), M (média), L (grande).
- **Risco**: baixo / médio / alto (de quebrar algo existente).
- **Critério**: qual critério de avaliação do desafio a melhoria reforça
  (Arquitetura, Governança, Guardrails, Tools, Dados sensíveis, Clean Code).

## Visão geral (fases e ordem recomendada)

| # | Item | Fase | Complex. | Risco | Depende de |
|---|------|------|----------|-------|-----------|
| 1 | Pré-agregação na ingestão ✅ | 1 Dados/Perf | M | médio | — |
| 2 | Migração p/ DuckDB + Parquet | 1 Dados/Perf | L | alto | 1 |
| 3 | Atualização automática do banco vivo ✅ | 1 Dados/Perf | M | médio | 1 |
| 4 | Guardrail anti prompt-injection (notícias) ✅ | 2 Segurança | S | baixo | — |
| 5 | Mascaramento ampliado + retenção de auditoria ✅ | 2 Segurança | S | baixo | — |
| 6 | Modo agente unificado na página ✅ | 3 Agente | M | médio | — |
| 7 | RAG mais forte (fontes + grounding) ✅ | 3 Agente | M | médio | 4 |
| 8 | Avaliação automatizada (tracing/regressão/backtest) ✅ | 3 Agente | M | baixo | 6,7 |
| 9 | Métrica de UTI real (CNES) + IC/suavização ✅ | 4 Métricas/UX | L | médio | 1 |
| 10 | Gráficos interativos (hover) ✅ + mapa/filtros (pend.) | 4 Métricas/UX | L | médio | 1 |
| 11 | Engenharia/CI (lint, tipos, cobertura, integração) ✅ | 5 Qualidade | M | baixo | — |

**Por que esta ordem:** primeiro a fundação de dados (1–3), que destrava desempenho
e "tempo real" e da qual várias outras dependem; depois segurança/governança (4–5),
que é barata e rende muito na avaliação; então a inteligência do agente (6–8);
em seguida métricas e UX (9–10), que são as mais visíveis; e por fim a malha de
qualidade/CI (11), que trava tudo o que foi feito.

---

## Fase 1 — Fundação de dados e desempenho

### 1. Pré-agregação na ingestão  ✅ CONCLUÍDO
- **O que muda**: além da tabela `srag`, o pipeline grava **tabelas-resumo** já
  agregadas (ex.: `agg_diario`, `agg_mensal`, `agg_faixa`, `agg_uf`, `agg_virus`),
  por data e dimensão. Métricas e gráficos passam a consultar os resumos.
- **Por quê**: hoje cada página lê linhas cruas; janelas de 2020-21 (~2M linhas)
  ficam lentas. Com resumos, qualquer data responde em milissegundos.
- **Arquivos**: `src/data_pipeline.py` (gerar os resumos ao salvar), `src/metrics.py`
  e `src/charts.py` (ler resumos em vez de linhas cruas), `src/config.py` (nomes das
  tabelas).
- **Necessidades**: nenhuma dependência nova.
- **Testes (TDD)**: paridade — as 4 métricas e as contagens dos gráficos calculadas
  via resumo batem exatamente com o cálculo sobre linhas cruas (mesmos fixtures).
- **Risco/mitigação**: médio (mudar a fonte das métricas). Mitigação: manter a função
  antiga sobre linhas cruas nos testes como "oráculo" de paridade.
- **Critério**: Arquitetura, Clean Code. **DoD**: resumos gravados, métricas/gráficos
  lendo dos resumos, testes de paridade verdes, tempo de página constante por data.

### 2. Migração de armazenamento para DuckDB + Parquet
- **O que muda**: os CSVs viram **Parquet** (tipado, comprimido) e as consultas usam
  **DuckDB** no lugar do SQLite. Ingestão continua em blocos.
- **Por quê**: leitura analítica muito mais rápida e menos memória; combina com os
  resumos do item 1.
- **Arquivos**: `src/data_pipeline.py` (escrever Parquet + tabela DuckDB),
  `src/metrics.py`/`src/charts.py` (conector DuckDB), `src/config.py`,
  `requirements.txt` (+`duckdb`, +`pyarrow`).
- **Necessidades**: libs `duckdb`, `pyarrow`. Espaço em disco para os Parquet.
- **Testes (TDD)**: mesma suíte de métricas/paridade rodando sobre DuckDB; teste de
  que a ingestão gera os Parquet esperados.
- **Risco/mitigação**: alto (troca a camada de dados). Mitigação: introduzir DuckDB
  atrás de uma função de acesso única (`carregar_dados`/`intervalo_datas`), para o
  resto do código não perceber a troca; manter fallback SQLite até a paridade fechar.
- **Observação**: o item 1 já entrega a maior parte do ganho de desempenho; este item
  é o passo de arquitetura para escalar. Pode ser adiado sem perda funcional.
- **Critério**: Arquitetura. **DoD**: suíte verde sobre DuckDB, Parquet gerados,
  memória/tempo medidos e documentados.

### 3. Atualização automática do banco vivo  ✅ CONCLUÍDO
- **O que muda**: um job agendado (semanal) baixa os CSVs dos anos vivos (2025/2026),
  reconstrói o banco e registra a data; a página mostra "última atualização".
- **Por quê**: o enunciado pede visão "em tempo real"; hoje o refresh é manual.
- **Arquivos**: novo `src/atualizar_dados.py` (download + `executar_pipeline`),
  `src/report.py` (selo de atualização), `src/config.py` (URLs/paths), agendamento
  (tarefa do SO ou o agendador do próprio ambiente).
- **Necessidades**: acesso de rede ao Open DATASUS; política de retentativa; as URLs
  estáveis dos recursos por ano.
- **Testes (TDD)**: download isolado (mockado) da lógica; teste de que, após um novo
  arquivo, a data de referência avança; parsing das URLs.
- **Risco/mitigação**: médio (rede/arquivos grandes). Mitigação: baixar para tmp,
  validar integridade antes de substituir o banco, e nunca deixar o banco num estado
  parcial (gravar novo e trocar atômico).
- **Critério**: Arquitetura, Tools. **DoD**: job roda ponta a ponta com um arquivo de
  teste, selo aparece na página, falha de rede não corrompe o banco.

---

## Fase 2 — Segurança e governança

### 4. Guardrail anti prompt-injection nas notícias  ✅ CONCLUÍDO
- **O que muda**: antes de mandar manchetes ao LLM/RAG, um guardrail as trata como
  **dado, não instrução**: remove/neutraliza padrões de injeção ("ignore as
  instruções", delimitadores, etc.) e encapsula o conteúdo como citação.
- **Por quê**: as notícias são conteúdo externo que hoje entra no prompt — é a única
  brecha de segurança real do sistema.
- **Arquivos**: `src/guardrails.py` (nova função `sanitizar_conteudo_externo`),
  `src/agent.py` e `src/report.py` (aplicar antes de compor o prompt/corpus).
- **Necessidades**: nenhuma dependência nova.
- **Testes (TDD)**: manchetes com tentativas de injeção são neutralizadas; manchete
  normal passa intacta; auditoria registra quando algo foi neutralizado.
- **Risco/mitigação**: baixo. Mitigação: apenas sanitiza a entrada externa, não altera
  a análise legítima.
- **Critério**: Guardrails, Governança. **DoD**: testes de injeção verdes, evento de
  auditoria emitido, prompt final comprovadamente sem instruções externas.

### 5. Mascaramento ampliado + retenção de auditoria  ✅ CONCLUÍDO
- **O que muda**: `sanitizar_saida` passa a mascarar também **CNS, telefone e e-mail**
  (não só CPF); o `Auditor` ganha **rotação/retenção** do `audit.jsonl` (tamanho/data).
- **Arquivos**: `src/guardrails.py` (novos padrões), `src/audit.py` (rotação).
- **Necessidades**: nenhuma dependência nova (regex + rotação simples).
- **Testes (TDD)**: cada tipo de identificador é mascarado; a rotação cria novo
  arquivo ao ultrapassar o limite e preserva o histórico.
- **Risco/mitigação**: baixo. Mitigação: regex conservadoras para não mascarar
  números legítimos das métricas (reusar a lógica de tolerância já existente).
- **Critério**: Dados sensíveis, Governança. **DoD**: novos padrões testados,
  rotação testada, documentação atualizada.

---

## Fase 3 — Inteligência do agente

### 6. Modo agente unificado na página  ✅ CONCLUÍDO
- **O que muda**: além do caminho determinístico, a página pode ser gerada pelo
  **agente ReAct (LangGraph)**, que decide as tools sozinho, com os mesmos guardrails
  e auditoria. Um parâmetro/rota escolhe o modo.
- **Por quê**: alinha o produto ao "agente orquestrador" do enunciado, mantendo a
  opção determinística (previsível/testável).
- **Arquivos**: `src/agent.py` (fluxo de geração via agente), `src/report.py`/
  `src/app.py` (seletor de modo), `src/config.py`.
- **Necessidades**: `ANTHROPIC_API_KEY` (já usado); nada novo.
- **Testes (TDD)**: com LLM mockado, o modo agente chama as tools e passa pelos
  guardrails; sem chave, cai no aviso honesto; auditoria registra as decisões.
- **Risco/mitigação**: médio (não-determinismo). Mitigação: guardrails e auditoria
  iguais aos do caminho atual; modo determinístico continua sendo o padrão.
- **Critério**: Arquitetura, Uso de Tools. **DoD**: os dois modos funcionam e são
  testados; página idêntica em estrutura nos dois.

### 7. RAG mais forte (fontes + grounding)  ✅ CONCLUÍDO
- **O que muda**: além do dicionário + Google Notícias, indexar **boletins
  epidemiológicos oficiais** e **múltiplas fontes de notícias** com deduplicação; a
  análise passa a **citar a fonte** do trecho usado (grounding).
- **Arquivos**: `src/tools/news_tool.py` (mais fontes + dedup), `src/knowledge.py`
  (boletins), `src/rag.py` (metadados de fonte no índice), `src/agent.py` (citação).
- **Necessidades**: URLs/feeds das fontes adicionais; rede. Depende do item 4 (todo
  conteúdo externo passa pelo guardrail de injeção).
- **Testes (TDD)**: dedup remove manchetes repetidas; recuperação devolve o trecho
  com a fonte; citação aparece na saída.
- **Risco/mitigação**: médio (fontes externas variam). Mitigação: parsing puro e
  testado; falha de uma fonte não derruba as demais.
- **Critério**: Tools, Governança (grounding). **DoD**: múltiplas fontes indexadas,
  dedup testado, citações na análise.

### 8. Avaliação automatizada (tracing, regressão, backtesting)  ✅ CONCLUÍDO
- **O que muda**: **tracing** das execuções do agente (LangSmith), **testes de
  regressão de prompt** (respostas estáveis para entradas fixas) e **backtesting**
  das métricas contra os painéis oficiais.
- **Arquivos**: config de tracing (`src/agent.py`), `tests/` (regressão/backtest),
  `requirements.txt` (opcional `langsmith`).
- **Necessidades**: conta/chave LangSmith (opcional; tracing desligável); valores de
  referência dos painéis oficiais para o backtest.
- **Testes (TDD)**: o próprio item é teste; regressão com LLM mockado + snapshots;
  backtest compara métricas com um conjunto de referência conhecido.
- **Risco/mitigação**: baixo. Mitigação: tracing opcional (sem chave, desliga);
  snapshots versionados.
- **Critério**: Governança/Transparência. **DoD**: tracing configurável, testes de
  regressão e backtest rodando no CI.

---

## Fase 4 — Métricas e experiência

### 9. Métrica de UTI real (CNES) + intervalos de confiança/suavização  ✅ CONCLUÍDO (IC + fallback; CNES a conectar)
- **O que muda**: a taxa de UTI deixa de ser proxy e passa a considerar a **capacidade
  de leitos (CNES)**; séries recentes ganham **suavização** e as taxas, **intervalos
  de confiança**.
- **Arquivos**: `src/metrics.py` (nova base de cálculo + IC), `src/config.py`, novo
  carregador da base CNES; `src/charts.py` (faixa de confiança nos gráficos).
- **Necessidades**: dados de leitos do CNES (fonte externa) e o mapeamento
  município/estabelecimento; definição estatística do IC.
- **Testes (TDD)**: cálculo do IC em casos conhecidos; suavização não altera a
  tendência; fallback para o proxy quando não há dado de leitos.
- **Risco/mitigação**: médio (nova fonte, interpretação). Mitigação: manter o proxy
  como fallback e rotular claramente o que é estimativa.
- **Critério**: (qualidade das métricas; reforça Arquitetura/Governança). **DoD**:
  métrica com IC, fonte CNES integrada, fallback testado, limitação documentada.

### 10. Gráficos interativos + mapa + filtros  ✅ interativo/hover CONCLUÍDO (mapa/filtros pendentes: precisam de GeoJSON)
- **O que muda**: gráficos passam a **interativos** (hover com valores) via Plotly ou
  Chart.js; entra um **mapa coroplético** por município/UF e **filtros** (UF, faixa,
  vírus) que recalculam o conteúdo.
- **Arquivos**: `src/charts.py` (ou novo `src/charts_web.py` que emite JSON/HTML em
  vez de PNG), `src/report.py` (montar os componentes + controles), `src/app.py`
  (endpoints de filtro).
- **Necessidades**: biblioteca JS via CDN (Plotly/Chart.js); GeoJSON de municípios/UF
  para o mapa. Depende dos resumos do item 1 para os filtros serem rápidos.
- **Testes (TDD)**: o endpoint devolve os dados esperados por filtro; o HTML inclui
  os componentes e os controles; limites dos filtros respeitados.
- **Risco/mitigação**: médio (mudança de PNG para interativo). Mitigação: manter os
  PNGs como fallback; introduzir um gráfico interativo por vez.
- **Critério**: Uso de Tools, Clean Code (na organização do front). **DoD**: hover
  funcionando, mapa e filtros operando sobre os resumos, testes verdes.

---

## Fase 5 — Malha de qualidade e CI

### 11. Engenharia/CI (sem Docker)  ✅ CONCLUÍDO
- **O que muda**: adicionar **ruff** (lint), **mypy** (tipos onde fizer sentido),
  **gate de cobertura** (pytest-cov), **matriz de versões do Python** e um **teste de
  integração** que sobe o servidor e bate em `/` e `/conteudo`. Tudo no CI existente.
- **Arquivos**: `.github/workflows/tests.yml` (jobs de lint/tipos/cobertura/matriz),
  `pyproject.toml`/`ruff.toml` (config), `tests/test_integracao.py`.
- **Necessidades**: `ruff`, `mypy`, `pytest-cov` no ambiente de CI.
- **Testes (TDD)**: o próprio CI é a verificação; o teste de integração sobe o app e
  valida as rotas.
- **Risco/mitigação**: baixo. Mitigação: começar o lint sem falhar o build (aviso),
  depois endurecer; tipos de forma incremental.
- **Critério**: Clean Code, Governança. **DoD**: CI com lint + tipos + cobertura
  mínima + matriz + integração, todos verdes.

---

## Necessidades transversais (consolidado)

- **Bibliotecas novas**: `duckdb`, `pyarrow` (item 2); `plotly` ou Chart.js via CDN
  (item 10); `langsmith` opcional (item 8); `ruff`, `mypy`, `pytest-cov` (item 11).
- **Dados externos**: URLs estáveis do Open DATASUS por ano (item 3); base de leitos
  **CNES** e GeoJSON de municípios/UF (itens 9 e 10); feeds/URLs de fontes extra de
  notícias e boletins (item 7).
- **Credenciais/contas**: `ANTHROPIC_API_KEY` (já existe); chave LangSmith **opcional**
  (item 8). Nenhuma vai para o repositório — só `.env`.
- **Rede**: itens 3 e 7 exigem internet; degradam com aviso honesto quando offline.
- **Espaço em disco**: Parquet (item 2) e os CSVs anuais (já baixados).

## Dependências entre itens

```
1 ──▶ 2        1 ──▶ 3
1 ──▶ 9        1 ──▶ 10
4 ──▶ 7
6,7 ──▶ 8
4, 5, 11: independentes (podem entrar a qualquer momento)
```

## Marcos sugeridos (entregas incrementais)

- **Marco A (Fundação)**: itens 1, 3 e — se aprovado o passo de arquitetura — 2.
  Resultado: desempenho constante e refresh semanal.
- **Marco B (Segurança)**: itens 4 e 5. Resultado: brecha de injeção fechada e
  mascaramento/retenção reforçados.
- **Marco C (Agente)**: itens 6, 7, 8. Resultado: agente na página, RAG com grounding,
  avaliação automatizada.
- **Marco D (Métricas/UX)**: itens 9 e 10. Resultado: UTI real e gráficos interativos.
- **Marco E (Qualidade)**: item 11. Resultado: CI endurecido.

## Como cada fase é verificada

Toda fase termina com: (1) a suíte `pytest` verde; (2) um smoke test do servidor
renderizando a página; (3) atualização deste plano e do `docs/DOCUMENTACAO.md`; e
(4) para itens que tocam métricas, um **teste de paridade** garantindo que os números
oficiais não mudaram.
