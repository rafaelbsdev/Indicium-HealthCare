# Documentação técnica — Agente de Relatório de SRAG

Este documento é a **fonte única de explicação** do projeto. O código-fonte foi
mantido deliberadamente limpo (sem comentários nem docstrings): os nomes das
funções e variáveis carregam o significado, e todo o "porquê" vive aqui.

Índice:

1. Visão geral e fluxo
2. Decisões de arquitetura
3. Módulo a módulo (função a função)
4. Guardrails, auditoria e LGPD
5. Estratégia de testes (TDD)
6. Limitações conhecidas
7. Trade-offs e o que faríamos com mais budget

---

## 1. Visão geral e fluxo

O sistema gera um **relatório de vigilância da SRAG** (Síndrome Respiratória
Aguda Grave). Um agente orquestrador consulta um banco de dados oficial, calcula
métricas, busca notícias em tempo real e produz um relatório com números,
gráficos e uma análise textual.

Fluxo de ponta a ponta:

```
CSV do DATASUS  →  data_pipeline (limpeza)  →  SQLite
                                                  │
                     metrics ─ calcula 4 métricas ┤
                     charts  ─ gera 5 gráficos     │
                     news_tool ─ busca notícias    │
                                                  ▼
                     agent ─ comenta (LLM + guardrails)
                                                  │
                                                  ▼
                     report ─ página (leve) + conteúdo (miolo, em memória)
                                                  │
                                                  ▼
        app ─ serve / (página) e /conteudo (atualização parcial por data)
```

Cada etapa é registrada pela **auditoria** (`audit`), e a saída do LLM passa
pelos **guardrails** antes de entrar no relatório.

---

## 2. Decisões de arquitetura

### 2.1 Data de referência configurável

O arquivo de exemplo é o banco de **2019**, mas o relatório pede métricas dos
"últimos 30 dias / 12 meses". Em vez de fixar uma data no código, o sistema usa
uma **data de referência**: por padrão (`DATA_REFERENCIA = None`), o último dia
presente nos dados é tratado como "hoje" (função `definir_data_referencia`).

Consequência: o mesmo código roda sem alteração tanto com o arquivo de 2019
quanto com o banco vivo de 2025/2026 (mesmo esquema de colunas). Para métricas
atuais, basta trocar o CSV em `data/` e apontar `RAW_CSV_PATH`.

### 2.2 O LLM nunca calcula números

Toda estatística é calculada em `metrics.py` (Python puro). O LLM (`agent.py`)
apenas **interpreta** os números que já vieram prontos. Isso é reforçado no
`SYSTEM_PROMPT` e **validado** pelos guardrails depois. É a defesa central contra
alucinação de dados num contexto sensível (saúde).

### 2.3 Tools desacopladas

As ferramentas do agente (`tools/agent_tools.py`) são adaptadores finos: elas só
chamam a lógica testável de `metrics`, `charts` e `news_tool`. A regra de negócio
nunca mora dentro da tool — fica nos módulos que os testes cobrem.

### 2.4 I/O separado de lógica pura

Onde há efeito colateral (rede, disco), separamos a parte pura da impura para
permitir testes sem dependências externas. Exemplo: em `news_tool`, `_baixar_rss`
(rede) é separado de `_parse_rss` (transformação pura). Em `agent`, a chamada ao
LLM fica isolada em `_invocar_llm`, que os testes substituem por um mock.

---

### 2.5 Privacidade por design (anonimização)
As bases do DATASUS já vêm **anonimizadas** (sem nome, CPF ou CNS) por força da
LGPD. Ainda assim, o arquivo traz **quase-identificadores** — data de nascimento,
sexo, raça, município, ocupação — que, combinados, poderiam permitir
reidentificação. Aplicamos duas defesas na **ingestão**, antes de qualquer dado
chegar ao banco ou ao LLM:

- **Minimização**: só carregamos as colunas necessárias; ocupação nem entra.
- **Generalização**: `DT_NASC` é reduzida ao ano (`ANO_NASC`); dia e mês são
  jogados fora. A idade das métricas vem de `IDADE_ANOS`.

Como defesa em profundidade, o pipeline ainda remove `PAC_COCBO`/`PAC_DSCBO` se
aparecerem, e a saída do LLM passa pelo guardrail que mascara CPF/nomes. Note que
o LLM **nunca** recebe linhas de paciente — só métricas agregadas e notícias.

### 2.6 Vários anos e desempenho (leitura em blocos + janela)
A base agora cobre **2019 a 2026** (mais de 5 milhões de casos; os CSVs somam
~4,7 GB, sendo 2020 e 2021 acima de 1 GB cada). Duas decisões tornam isso viável:

- **Ingestão em blocos, só as colunas necessárias**: cada CSV é lido em pedaços
  (`CHUNKSIZE`) e apenas com as ~17 colunas úteis (`usecols` em lista). Cada bloco
  é limpo, anonimizado e **acrescentado** ao SQLite; entre arquivos, o cache de
  disco é liberado. A memória fica constante, independente do tamanho do arquivo.
- **Pré-agregação (leitura O(dias), não O(linhas))**: na ingestão, além de `srag`,
  gravamos tabelas-resumo por dia (`agg_diario`, `agg_faixa`, `agg_uf`, `agg_virus`).
  A página lê **só esses resumos** (poucos milhares de linhas), então qualquer data —
  inclusive o pico de 2020-21 — responde em ~1 s com uso de memória baixo. Medição
  real da janela de 2021: caiu de ~3,7 GB / 19 s (lendo linhas cruas) para **~124 MB
  / 1,5 s**. A paridade com o cálculo cru é garantida por teste.
- **Leitura por janela no relatório**: a página não carrega os 5,5 milhões de
  registros. Ela descobre o intervalo com `intervalo_datas()`, resolve a data de
  referência e então carrega via `carregar_dados(desde=ref − 13 meses)` — só o
  necessário para as métricas (janelas de 30 dias e 12 meses) e os gráficos. Isso
  derruba o uso de memória de ~3,7 GB para algumas centenas de MB por página.

Sobre tokens: o LLM **nunca** recebe o arquivo nem linhas de paciente — recebe as
métricas já agregadas e as manchetes. A minimização de colunas na ingestão garante
que nem a etapa de processamento carrega dado além do necessário.

## 3. Módulo a módulo

### `config.py`
Configuração central. Não tem lógica — só constantes:

- `BASE_DIR`, `DATA_DIR`, `REPORTS_DIR`, `LOGS_DIR`: caminhos do projeto.
- `DB_PATH`: caminho do SQLite. Pode ser sobrescrito pela variável de ambiente
  `SRAG_DB_PATH` (útil quando a pasta está em um sistema de arquivos que não
  suporta bem o SQLite).
- `RAW_CSV_PATH`, `TABLE_NAME`: arquivo de referência e nome da tabela.
- `RAW_CSV_DIR`, `RAW_CSV_GLOB` (`INFLUD*.csv`): pasta e padrão para achar **todos
  os anos** de uma vez (2019–2026). Basta jogar os CSVs em `data/`.
- `CHUNKSIZE`: quantas linhas por bloco na leitura (ver 2.6). Arquivos grandes
  (2020/2021 têm mais de 1 GB) são lidos em pedaços para não estourar a memória.
- `COLUNAS_USADAS`: das ~194 colunas do CSV, só carregamos estas (~17): datas,
  desfecho, UTI, vacina, classificação final, UF, idade e nascimento. É
  **minimização de dados** — menos ruído e menos dado sensível em memória.
  Ocupação (`PAC_COCBO`/`PAC_DSCBO`) fica de fora de propósito.
- `COLUNAS_SENSIVEIS_REMOVER`, `TP_IDADE_ANO`: apoiam a anonimização (ver 2.5).
- `CLASSI_FIN_NOMES`: traduz o código da classificação final (1 = influenza …
  5 = COVID-19) para o rótulo dos gráficos.
- `FAIXAS_ETARIAS_LIMITES` / `_ROTULOS`, `TOP_UF`: parâmetros dos gráficos novos.
- `COLUNAS_DATA`: colunas convertidas de texto para data.
- `EVOLUCAO_OBITOS = {"2","3"}`: no dicionário do DATASUS, 2 = óbito e
  3 = óbito por outras causas.
- `EVOLUCAO_DESFECHO_CONHECIDO = {"1","2","3"}`: casos encerrados (1 = cura).
- `SIM = "1"`, `NAO = "2"`, `IGNORADO = "9"`: códigos usados em UTI, VACINA etc.
- `DATA_REFERENCIA`, `JANELA_CURTA_DIAS`, `JANELA_LONGA_MESES`: parâmetros das
  janelas de tempo.

### `data_pipeline.py`
Transforma o CSV bruto e sujo em um SQLite limpo.

- `listar_csvs()`: acha todos os `INFLUD*.csv` da pasta `data/`, em ordem. É o
  que permite **consolidar vários anos** num banco só.
- `_colunas_presentes(caminho)`: lê só o cabeçalho e devolve, das `COLUNAS_USADAS`,
  as que existem naquele arquivo (anos têm pequenas diferenças de layout).
- `carregar_csv(caminho)` / `ler_em_blocos(caminho)`: leem com `;` e **tudo como
  texto** (`dtype=str`). O `usecols` recebe a **lista** das ~17 colunas necessárias,
  então o parser lê só elas — economia enorme de memória (17 de 194 colunas) e o
  que dá para processar arquivos de 1,7 GB. `ler_em_blocos` devolve em pedaços
  (`chunksize`) para a memória ficar constante.
- `limpar(df)`: o coração do tratamento (roda por bloco).
  1. Converte as colunas de data; `errors="coerce"` transforma data inválida em
     `NaT` em vez de quebrar. As datas vêm em ISO com fuso (`...Z`), então
     usamos `utc=True` e removemos o fuso.
  2. Remove **datas impossíveis** (antes de 2009 — início da vigilância — ou no
     futuro). Nos dados reais achamos `DT_INTERNA` no ano **2109**.
  3. Descarta registros sem `DT_SIN_PRI` (data dos primeiros sintomas), que é a
     espinha dorsal da série temporal.
  4. **Normaliza códigos**: dado sujo real — `EVOLUCAO` vem como `"2.0"` e `UTI`
     como `"2"`. O `.str.replace(r"\.0$", "")` uniformiza para bater com o
     dicionário.
  5. **Deriva `IDADE_ANOS`** de `NU_IDADE_N` + `TP_IDADE` (idade em meses ou dias
     vira 0 = menor de 1 ano; só `TP_IDADE = 3` conta como anos).
  6. **Anonimiza** (`anonimizar`): `DT_NASC` é generalizada para só o **ano**
     (`ANO_NASC`) — dia e mês são descartados; ocupação (`PAC_COCBO`/`PAC_DSCBO`)
     é removida se estiver presente. Ver 2.5.
  7. Cria `DATA_CASO` (só a data dos primeiros sintomas, sem hora) para agrupar.
- `derivar_idade(df)` e `anonimizar(df)`: funções puras, testadas isoladamente.
- `salvar_sqlite(df, substituir)`: grava a tabela e mantém um índice em `DATA_CASO`.
  Com `substituir=True` recria a tabela (primeiro bloco); com `False` **acrescenta**
  — é o que permite empilhar bloco após bloco e ano após ano.
- `_liberar_cache_do_disco(caminho)`: depois de cada arquivo, pede ao SO para
  soltar o cache daquele CSV (`posix_fadvise`). Sem isso, o cache dos anos já lidos
  soma com o próximo arquivo grande e estoura a memória. Em Windows a função não
  existe e a chamada vira um no-op (protegida por `hasattr`).
- `enriquecer(df)`: adiciona por linha as **bandeiras** que as métricas usam
  (`EH_OBITO`, `EH_DESFECHO`, `UTI_SIM/CONHECIDO`, `VACCOV_*`, `VACGRIPE_*`) e a
  `FAIXA` etária. Calculadas em pandas com os mesmos critérios das métricas — é o que
  garante paridade quando somadas.
- `construir_agregados(conn)`: ao fim da carga, cria as **tabelas-resumo**
  (`agg_diario`, `agg_faixa`, `agg_uf`, `agg_virus`) com um `GROUP BY` sobre `srag`.
  São minúsculas (milhares de linhas) e é delas que a página lê (ver 2.6).
- `executar_pipeline(caminhos=None, substituir=True)`: orquestra tudo — para cada
  arquivo, lê em blocos, limpa, grava (primeiro substitui, depois acrescenta) e
  libera o cache. Sem argumentos, processa **todos** os CSVs da pasta.

### `metrics.py`
Calcula as 4 métricas. **Nenhum número sai daqui sem numerador, denominador e um
texto explicando a conta** — isso é transparência para auditoria.

- `Metrica` (dataclass): guarda nome, valor, unidade, numerador, denominador e
  detalhe. O método `resumo()` formata uma linha legível.
- `ResultadoMetricas` (dataclass): agrega a data de referência, o total de casos
  na janela e o dicionário de métricas.
- `carregar_dados(desde=None)`: lê o SQLite reconvertendo as datas. Com `desde`,
  filtra **no SQL** (`WHERE DATA_CASO >= …`) e traz só a janela necessária — com
  5,5 milhões de linhas, carregar tudo a cada página seria inviável (ver 2.6).
- `intervalo_datas()`: devolve (data mínima, máxima) com uma consulta leve — usada
  pelo date picker e para achar a data de referência sem ler a base inteira.
- `definir_data_referencia(df)`: ver seção 2.1.
- `taxa_aumento_casos(df, ref)`: variação percentual entre os casos da última
  janela de 30 dias e os 30 dias anteriores. Se a janela anterior não tem casos,
  a variação é indefinida (`valor = None`).
- `taxa_mortalidade(df)`: óbitos ÷ casos com desfecho **conhecido**. Casos em
  aberto ficam fora do denominador para não distorcer.
- `taxa_ocupacao_uti(df)`: casos que foram para UTI ÷ casos com status de UTI
  conhecido. (Ver limitação 6.1.)
- `taxa_vacinacao(df)`: vacinados ÷ casos com status conhecido. Usa a coluna de
  vacina COVID quando há dado suficiente (≥ 1% da base); senão cai para a vacina
  da gripe. No arquivo de 2019, a coluna COVID é quase vazia (a vacina não
  existia), então a escolha automática cai na gripe.
- `calcular_todas(df=None, ref=None)`: orquestra tudo. Aceita uma **data de
  referência** explícita (`ref`) — usada pelo date picker da página; sem ela, usa
  a data máxima dos dados. As métricas de proporção (mortalidade, UTI, vacinação)
  são calculadas sobre a janela dos últimos 12 meses até a referência; o aumento
  de casos usa a janela de 30 dias.

### `charts.py`
Gera os gráficos do relatório (os 2 exigidos + 3 de perfil).

- `grafico_casos_diarios(df, ref)`: casos por dia nos últimos 30 dias. Reindexa a
  série para incluir dias sem casos como zero (senão o eixo "pularia" dias).
- `grafico_casos_mensais(df, ref)`: casos por mês nos últimos 12 meses, também
  reindexado para meses sem casos.
- `grafico_faixa_etaria(df, ref)`: barras de **casos e óbitos por faixa etária**
  (0-9, 10-19 … 80+), usando `IDADE_ANOS` e marcando óbito por `EVOLUCAO ∈ {2,3}`.
  Cada barra recebe um **rótulo com o valor** (ex.: `167.3k`, `442`), para os números
  ficarem legíveis mesmo quando as escalas são muito diferentes.
- `grafico_tipo_virus(df, ref)`: casos por **classificação final** (`CLASSI_FIN`
  → influenza, outro vírus, COVID-19 …). Em 2019 não há COVID, então o código 5
  simplesmente não aparece.
- `grafico_geografico(df, ref)`: casos por **estado** (top `TOP_UF` UFs de notificação).
- `gerar_todos(df, ref)`: gera os **cinco** e devolve os **bytes PNG** de cada um.
- Detalhe técnico: os gráficos são renderizados **em memória** (`io.BytesIO`), sem
  tocar o disco, e usamos `matplotlib.use("Agg")` (backend sem tela) para rodar em
  servidor/CI. Os bytes são embutidos como base64 no HTML pelo `report.py`.

### `agregados.py`
A camada de leitura rápida do relatório. Em vez de ler milhões de linhas cruas a
cada página, lê as **tabelas-resumo** (todas com poucos milhares de linhas) e:

- `calcular_metricas(ref)`: reproduz as 4 métricas a partir de `agg_diario` (somando
  as bandeiras na janela) — devolve o mesmo `ResultadoMetricas` de `metrics`.
- `series_graficos(ref)` / `gerar_graficos(ref)`: montam as séries dos 5 gráficos a
  partir dos resumos e chamam os `render_*` de `charts`.
- `intervalo_datas()`: mínimo/máximo a partir de `agg_diario` (consulta leve).

`metrics.py` continua existindo como **oráculo**: ele calcula sobre linhas cruas e é
o que os testes de paridade (`tests/test_agregados.py`) usam para provar que o
caminho agregado dá exatamente os mesmos números.

### `charts.py`
Além dos `grafico_*` (que recebem linhas cruas, usados nos testes), o módulo separa
**cálculo da série** (`_serie_*`) de **renderização** (`render_*`). Os `render_*` são
compartilhados: tanto o caminho cru quanto o agregado (`agregados`) produzem a mesma
série e chamam o mesmo render — por isso o gráfico é idêntico nos dois caminhos.

### `audit.py`
Registro de auditoria em formato **JSON Lines** (um objeto JSON por linha) — fácil
de reprocessar depois.

- `Auditor`: abre `logs/audit.jsonl` em modo *append* (nunca sobrescreve).
- `registrar(evento, **dados)`: grava a linha com timestamp UTC.
- Atalhos semânticos (`tool_chamada`, `tool_resultado`, `guardrail`,
  `decisao_llm`, `erro`) deixam o código de quem audita mais legível.
- **Retenção**: ao passar de `AUDIT_MAX_BYTES`, o `audit.jsonl` é **rotacionado**
  (renomeado com carimbo de data) e um novo arquivo começa — o log não cresce sem limite.

### `rag.py`
O **RAG completo** (Retrieval-Augmented Generation) com banco vetorial.

- `dividir_em_chunks(texto)`: quebra textos longos em pedaços (pura, testável);
  textos curtos (manchetes, campos do dicionário) viram um único chunk.
- `IndiceMemoria`: índice vetorial em memória com similaridade de cosseno. Usado
  nos testes e como fallback sem dependências pesadas.
- `IndiceChroma`: índice persistente usando **Chroma** (banco vetorial de
  produção). Importado sob demanda.
- `EmbedderLocal`: gera embeddings com **sentence-transformers** (modelo
  `all-MiniLM-L6-v2`), 100% local, sem chave de API. Importado sob demanda.
- `RagContexto`: orquestra indexar (chunk → embed → índice) e recuperar (embed da
  consulta → busca top-k).
- `criar_embedder_padrao()`: tenta construir o `EmbedderLocal`; devolve `None` se
  as bibliotecas pesadas não estiverem instaladas.
- `montar_contexto(textos, consulta, k)`: ponto de entrada usado pelo relatório —
  indexa o corpus e recupera os trechos mais relevantes. Se não há embedder
  disponível, faz fallback para concatenar os textos (o projeto continua rodando).

**Design injetável:** embedder e índice são parâmetros. Nos testes, um embedder
falso determinístico + `IndiceMemoria` cobrem a lógica sem `torch`/Chroma; em
produção usa-se `EmbedderLocal` + `IndiceChroma`.

### `knowledge.py`
`DICIONARIO_CAMPOS`: descrições curadas dos campos do DATASUS que o projeto usa
(EVOLUCAO, UTI, VACINA, CLASSI_FIN, etc.), extraídas do dicionário oficial. Este
é o corpus do dicionário que o RAG indexa junto com as notícias, permitindo ao
agente explicar o significado técnico dos campos.
`FONTES_OFICIAIS` acrescenta ao corpus descrições de fontes oficiais (InfoGripe,
boletins do Ministério da Saúde, SIVEP-Gripe), para o RAG ancorar a análise em
referências confiáveis além das manchetes.

### `tools/news_tool.py`
Notícias de SRAG em tempo real via RSS do Google Notícias (sem chave de API). As
manchetes são um dos corpora do RAG (o outro é o dicionário).

- `montar_url(consulta)`: monta a URL do feed em pt-BR.
- `_baixar_rss(url)`: a parte de **rede** (impura, não testada em unidade).
- `_parse_rss(xml)`: a parte **pura** — converte o XML em objetos `Noticia`.
  Testada com um XML de exemplo. Detalhes: a tag `<source>` é buscada com
  `item.find("source")` e não com `x or y`, porque um elemento XML sem filhos é
  "falsy" no ElementTree e o `or` daria o resultado errado (bug pego por teste);
  e o **sufixo "- Fonte"** que o Google Notícias coloca no fim do título é
  removido, para não duplicar o nome da fonte (que já vira hyperlink na página).
- `buscar_noticias(...)`: consulta **múltiplas fontes** (várias buscas em
  `CONSULTAS`: SRAG, InfoGripe/Fiocruz, surtos), junta os resultados e aplica
  `deduplicar` (mesmo título vindo de feeds diferentes vira um só); ordena por data e
  corta em **10**. Uma fonte que falhar não derruba as demais.
- `deduplicar(noticias)`: remove manchetes repetidas por título normalizado.
- `ordenar_por_data(noticias)`: ordena da mais **recente** para a mais antiga
  (datas inválidas/desconhecidas vão para o fim).
- `noticias_como_texto(...)`: formato **texto** (usado no prompt do LLM e no corpus
  do RAG); devolve mensagem amigável se a lista estiver vazia.
- `noticias_como_html(...)`: formato **HTML** — cada manchete (`<li class="nt-item">`)
  com o **nome da fonte como hyperlink** (`target="_blank" rel="noopener noreferrer"`)
  que leva à notícia.

> A **paginação** da seção de notícias é feita no navegador (ver `report._secao_noticias`):
> as até 10 notícias já vêm na página e o JS mostra 5 por vez, com um indicador
> os botões Anterior/Próxima — sem novo acesso ao servidor nem recomputar o relatório.

> **Requisito de rede:** a seção de notícias só é preenchida quando há **acesso à
> internet**. Em ambientes sem saída para a internet (por exemplo, atrás de um
> proxy que bloqueia o feed, ou em sandboxes de CI), o download do RSS falha e a
> seção mostra "Nenhuma notícia recente foi recuperada" — sem quebrar o relatório.
> Numa máquina com internet, o Google Notícias responde e a seção enche
> normalmente.

### `tools/agent_tools.py`
As três ferramentas no formato LangChain (`@tool`).

- A descrição de cada tool é passada em `description=` (não como docstring). Isso
  é **dado funcional**: é o texto que o agente usa para decidir quando chamar a
  ferramenta — por isso permanece no código, mesmo com o resto limpo.
- `consultar_metricas()`: chama `metrics.calcular_todas()` e devolve o resumo.
- `gerar_graficos()`: gera os dois gráficos e devolve os caminhos.
- `consultar_noticias()`: busca notícias; em caso de falha de rede, devolve uma
  mensagem amigável em vez de quebrar o agente.

### `agent.py`
O agente orquestrador (LangGraph + Claude).

- `SYSTEM_PROMPT`: as regras de comportamento do agente (só citar números reais,
  usar notícias só como contexto, nunca citar dado individual). É dado funcional.
- `construir_llm()`: cria o cliente do Claude (requer `ANTHROPIC_API_KEY`).
- `construir_agente_react()`: monta o agente ReAct com as três tools.
- `_invocar_llm(system, user)`: isola a chamada ao modelo (substituída por mock
  nos testes).
- `_aviso_indisponivel(motivo)`: devolve uma mensagem **honesta** de "Análise
  indisponível" — usada quando a análise por LLM não pode ser feita. Nunca finge
  ser uma análise real.
- `comentar_metricas(resultado, noticias, auditor)`: o fluxo com governança. A
  análise do cenário é **sempre feita pelo LLM (Claude)**. Se o LLM não estiver
  disponível, mostra o aviso honesto em vez de um texto que pareça análise:
  - sem `ANTHROPIC_API_KEY` → aviso pedindo para configurar a chave;
  - falha na chamada da API (rede, chave expirada, sem crédito) → capturada por
    `try/except` e transformada em aviso, sem quebrar o relatório;
  - o LLM cita um número que não confere com as métricas → a análise **não é
    descartada**; ela é preservada e ganha uma observação nomeando o valor não
    verificado (ver política do guardrail na seção 4).
  Todos os caminhos são registrados na auditoria.
- `comentar_metricas_via_agente(resultado, auditor)`: o **modo agente**. Em vez de um
  prompt fixo, executa o **agente ReAct (LangGraph)**, que decide sozinho chamar as
  tools (`consultar_metricas`, `consultar_noticias`) e escreve a análise. A saída
  passa pelo **mesmo** pós-processamento de guardrails (`_pos_processar_analise`:
  mascaramento + anti-alucinação com preservar-e-sinalizar), e os mesmos avisos
  honestos valem quando não há chave ou o agente falha.
- `_pos_processar_analise(...)`: os guardrails de saída compartilhados pelos dois
  modos — garante que determinístico e agente têm exatamente a mesma proteção.

A página escolhe o modo por um parâmetro: `report.construir_conteudo(modo=...)` e a
rota `/conteudo?modo=agente` (via `app.py`), com um **seletor "Modo agente"** no
cabeçalho. O **determinístico** é o padrão (previsível e testável); o agente é a
opção "100% agêntica" pedida pelo enunciado.

### `report.py`
**Constrói o HTML do relatório** e o devolve como **string** — nada é escrito em
disco. Separado em duas partes para permitir atualização parcial:

- `construir_pagina()`: monta a **página persistente** (leve): cabeçalho fixo com
  título, **date picker** (valor padrão = **data mais recente**, limitado ao
  período dos dados) e o botão "Atualizar dados", mais um `<main id="conteudo">`
  vazio e o JS que carrega o conteúdo via `fetch("/conteudo?...")`. É rápida porque
  não calcula métricas/gráficos/análise — só consulta o intervalo de datas.
- `construir_conteudo(data_ref=None)`: monta só o **miolo** (métricas, gráficos,
  análise, notícias + a linha de metadados e o aviso de data). É a parte pesada.
  Quando o usuário troca a data ou clica em "Atualizar", **só este fragmento é
  recarregado** (com um spinner local), mantendo o cabeçalho fixo — sem o "flash"
  de recarregar a página inteira e sem re-buscar notícias/re-rodar o LLM à toa.
  Detalhe: o JS da página **re-executa os `<script>`** injetados no fragmento
  (`innerHTML` não roda scripts), para a paginação de notícias funcionar.

- `_img(png_bytes)`: converte os bytes de um gráfico em `data:image/png;base64,…`,
  embutindo a imagem direto no HTML (a página é autocontida, sem arquivos soltos).
- `_cards(res)`: monta os cartões das 4 métricas.
- `_md_para_html(texto)` (e `_inline`): converte o **Markdown** que o LLM produz na
  análise (títulos `#`, negrito `**…**`, listas `- …`, parágrafos) em HTML, para o
  texto ficar bem formatado na página em vez de mostrar a marcação crua.
- `_secao_noticias(noticias, por_pagina=5)`: monta a seção de notícias **paginada**.
  Renderiza todas as (até 10) manchetes e injeta um JS que mostra 5 por página, com
  um indicador **"página / total"** (ex.: `2 / 2`) e botões Anterior/Próxima — ao clicar
  em Próxima, revela as próximas 5. Guardas: "Anterior" fica desabilitado na
  página 1 (nunca vai a 0/−1) e "Próxima" na última (nunca passa do total).
- `_resolver_ref(min_d, max_d, data_ref)`: decide a **data de referência** a partir
  do intervalo (obtido por `metrics.intervalo_datas()`, consulta leve). Sem data,
  usa a máxima. Com uma data do date picker, valida contra `[min, max]`: fora (ou
  inválida) → **aviso** e cai para o período mais recente; dentro → usa a escolhida.
  Em seguida `construir_conteudo` carrega **só a janela** `desde = ref − 13 meses`.
- `_fontes_consultadas(noticias)`: monta o rodapé **"Fontes consultadas"** com as
  fontes distintas (com link) que embasaram o contexto — é o **grounding** visível da
  análise, independente do que o LLM escreva.
- `construir_conteudo(data_ref=None)`: monta só o **miolo** do relatório — resolve
  a data, calcula as 4 métricas, gera os 5 gráficos (em memória), busca notícias,
  monta o contexto RAG, pede a análise ao LLM e devolve o **fragmento** HTML (sem
  `<html>`/`<head>`). Tudo é auditado (`inicio_html`/`fim_html`).
- `construir_pagina()`: monta a **página persistente** — cabeçalho com o date
  picker (padrão = data mais recente), a área `#conteudo` e o JS que busca o
  fragmento em `/conteudo` e troca só o miolo, sem recarregar o cabeçalho.

### `app.py` e `main.py`
- `app.py`: servidor HTTP da biblioteca padrão (`http.server`). Rota `/` devolve a
  **página persistente**; `/conteudo?data=…&atualizar=…` devolve o **miolo**. Há um
  cache por data (`_CACHE`) para não repetir a chamada ao LLM a cada troca. `iniciar`
  sobe o servidor e abre o navegador.
- `main.py`: a CLI. `--construir-banco` roda o pipeline; `--agente "pergunta"` usa o
  agente ReAct; sem argumentos, sobe o servidor do relatório.
- `make_diagram.py`: gera o `docs/arquitetura.pdf` (diagrama conceitual exigido).
- `main.py` também aceita `--atualizar` (baixa os anos vivos e reconstrói o banco).

### `atualizar_dados.py`
Atualização automática do "banco vivo" (o enunciado pede visão em tempo real).

- `resolver_url(resource_id)`: consulta a **API CKAN** do Open DATASUS
  (`resource_show`) e devolve a URL atual do CSV daquele ano — o link direto muda a
  cada semana, então resolvemos pelo id estável do recurso.
- `baixar_arquivo(url, destino)`: baixa em `.part` e só então **renomeia** (download
  atômico — nunca deixa um arquivo pela metade no lugar do bom).
- `atualizar(...)`: para cada ano vivo (2025/2026, ver `RECURSOS_VIVOS`), remove o CSV
  antigo daquele ano, baixa o novo e roda `executar_pipeline()` — que reconsolida
  **todos** os anos presentes em `data/` e regrava os agregados e o metadado
  `construido_em`. A rede fica isolada (parâmetros `resolver`/`baixar`), então os
  testes rodam sem internet.
- O relatório mostra um selo **"Base atualizada em …"** lido do metadado.

**Como agendar** (fora do código, no SO):
- Windows: Agendador de Tarefas → nova tarefa semanal executando
  `python src/main.py --atualizar` na pasta do projeto.
- Linux/macOS: uma entrada `cron` semanal com o mesmo comando.
Os CSVs dos anos congelados (2019-2024) devem permanecer em `data/` para entrarem na
reconsolidação.

---

## 4. Guardrails, auditoria e governança (LGPD)

Estes três pilares atendem diretamente aos critérios de avaliação
**Governança/Transparência**, **Guardrails** e **Tratamento de dados sensíveis**.

### 4.1 Auditoria (transparência)
Toda decisão relevante é gravada em `logs/audit.jsonl` (JSON Lines, *append*, com
timestamp UTC). Registramos: início/fim da geração, resultado de cada tool
(métricas, gráficos, notícias, contexto RAG), as **decisões dos guardrails**, o
caminho seguido pela análise do LLM e os erros capturados. Como é uma linha JSON
por evento, dá para reprocessar/auditar depois sem parser especial. É a resposta ao
critério "mecanismos de auditoria e registro de decisões dos agentes".

### 4.2 Guardrails (`guardrails.py`)
- `validar_escopo(texto)`: mantém a resposta **no tema** (SRAG/saúde), evitando que
  o agente seja desviado para assuntos fora do escopo.
- `validar_numeros_do_texto(texto, valores_permitidos, tolerancia)`: a defesa
  central **anti-alucinação**. Extrai os números que o LLM escreveu e confere cada
  um contra as métricas oficiais calculadas. A comparação é por **magnitude** (com
  tolerância), para não gerar falso positivo por sinal ou arredondamento.
  **Política "preservar e sinalizar"**: se um número não confere, a análise **não é
  descartada** — ela é mantida e recebe uma observação nomeando o valor suspeito e
  pedindo conferência. Descartar a análise inteira por causa de um número seria pior
  para o usuário do que mostrá-la com um alerta honesto.
- `sanitizar_conteudo_externo(texto)`: **anti prompt-injection**. As manchetes são
  conteúdo externo que entra no prompt/RAG; esta função as trata como **dado, não
  instrução**: remove delimitadores (```` ``` ````, `<`, `>`) e neutraliza frases de
  injeção ("ignore as instruções", "you are now", `system:` etc.), devolvendo o texto
  limpo e um sinal `alterado`. O `report` aplica isso antes de montar o corpus e
  **audita** quando neutraliza algo (`guardrail: prompt_injection`).
- `validar_sem_dado_sensivel(texto)` / `sanitizar_saida(texto)`: **rede de segurança
  na saída** — varrem o texto **gerado pelo LLM** e mascaram qualquer coisa com
  formato de **CPF, CNS, telefone, e-mail** ou nome individual. Atenção: isso **não** é porque a entrada tenha
  identificadores (ela já vem anonimizada — ver 4.3); é defesa em profundidade, para
  o caso de o modelo inventar um valor ou de uma fonte futura ser menos limpa. Por
  isso quase nunca dispara.

### 4.3 Dados sensíveis / LGPD
Ver também a seção 2.5. Em resumo, três camadas: **minimização** (só ~17 de 194
colunas entram; ocupação nem é carregada), **generalização** na ingestão (`DT_NASC`
vira só o ano; dia e mês são descartados) e **agregação** (o relatório só expõe
contagens e taxas, nunca um indivíduo). O LLM jamais recebe linhas de paciente — só
métricas agregadas e manchetes. Além disso, as bases do DATASUS já vêm anonimizadas
(sem nome/CPF/CNS) por força da Lei 13.709/2018; nosso tratamento é defesa em
profundidade sobre os **quase-identificadores** que restam.

São **camadas distintas** e complementares, não redundância: a anonimização e a
minimização (4.3) garantem que nenhum identificador direto **entra** no pipeline; o
mascaramento de saída (`sanitizar_saida`, 4.2) protege o que **sai** do LLM. Uma é
sobre o dado de entrada; a outra, sobre o texto gerado.

---

## 5. Estratégia de testes (TDD)

O projeto foi escrito em **TDD** (red → green → refactor): cada comportamento nasceu
de um teste que falhava antes de existir o código. São **82 testes** (`pytest`) e
rodam **sem rede, sem chave de API e sem bibliotecas pesadas** (`torch`/Chroma),
graças à separação entre I/O e lógica pura e ao uso de mocks.

Cobertura, por área:
- **Métricas**: as 4 taxas com casos-limite (janela anterior vazia, sem desfecho
  conhecido, escolha COVID vs gripe, data de referência explícita).
- **Tratamento e anonimização**: remoção de datas impossíveis, normalização de
  códigos ("2.0" → "2"), `DT_NASC` → ano, remoção de ocupação, derivação de idade,
  leitura **multi-ano em blocos** e concatenação, `usecols` só das colunas úteis.
- **Gráficos**: cada um devolve **bytes PNG** válidos (sem tocar disco/tela).
- **Guardrails**: escopo, conferência numérica por magnitude, mascaramento.
- **Notícias**: parsing puro do RSS (com o bug do `<source>` "falsy" coberto),
  ordenação por data, remoção do sufixo de fonte, tratamento de falha de rede.
- **Auditoria**: gravação em JSON Lines.
- **RAG**: chunking, índice em memória (cosseno), recuperação top-k, com um embedder
  falso determinístico (sem `torch`).
- **Agente e relatório**: LLM mockado; aviso honesto quando indisponível; fragmento
  vs página; contagem de imagens; guardas da paginação de notícias.
- **App e CLI**: roteamento das rotas e os três modos do `main`.

Infra: `pytest.ini` aponta `pythonpath=src`; `conftest.py` provê fixtures de dados
sintéticos, banco SQLite temporário e pasta de logs temporária.

---

## 6. Limitações conhecidas

- **Taxa de ocupação de UTI é um *proxy***: o dado é um sinalizador por caso (o
  paciente foi ou não à UTI), não a ocupação real de leitos. Sem cruzar com a
  capacidade de leitos (CNES), é uma aproximação — está documentado como tal.
- **Taxa de vacinação**: a base escolhe automaticamente entre vacina COVID e gripe
  conforme o preenchimento; a interpretação muda com essa escolha (indicada no
  detalhe da métrica).
- **Qualidade do dado recente**: as semanas mais recentes sofrem *atraso de
  notificação* e subnotificação; o "banco vivo" é revisado retroativamente. Métricas
  das últimas semanas podem subir depois.
- **Desempenho em janelas históricas pesadas**: *resolvido* pela pré-agregação
  (seção 2.6). A página lê tabelas-resumo em vez de linhas cruas, então qualquer data
  responde em ~1 s. (Antes, a janela de 2020-21 lia ~2 milhões de linhas e ficava
  lenta.)
- **Notícias**: dependem de internet e de **uma** fonte (RSS do Google Notícias),
  usadas só como contexto — não entram no cálculo das métricas.
- **Análise textual**: qualidade limitada pelo modelo/prompt e requer chave de API;
  sem ela, o relatório continua completo, só sem o comentário.
- **Anonimização**: reduz quase-identificadores, mas não é uma garantia formal de
  *k-anonimato*.

---

## 7. Trade-offs e o que faríamos com mais budget

### 7.1 Trade-offs assumidos
- **Servidor com a biblioteca padrão + HTML embutido**, em vez de FastAPI/React.
  Ganho: zero dependências de web, simples de rodar e auditar. Custo: menos
  componentização e escalabilidade.
- **SQLite**, em vez de Postgres/DuckDB. Ganho: arquivo único, sem servidor. Custo:
  em análises sobre milhões de linhas, um DuckDB sobre Parquet seria bem mais rápido.
- **Orquestração determinística na página**: o relatório chama as tools em ordem
  fixa (métricas → gráficos → notícias → RAG → LLM) e aplica os guardrails. O
  **agente ReAct (LangGraph)** existe e decide as tools sozinho via `--agente`, mas a
  página usa o caminho determinístico. Ganho: previsibilidade e testabilidade de um
  produto. Custo: o fluxo "100% agêntico" fica no modo CLI, não na página.
- **RAG local** (sentence-transformers + Chroma/memória) em vez de embeddings por
  API. Ganho: sem custo e sem chave para o RAG. Custo: corpus pequeno e curado.
- **Guardrail "preservar e sinalizar"** em vez de descartar. Ganho: não perde uma
  análise boa por um número; Custo: exige que o usuário leia a observação.
- **Carregamento por janela** em vez da base inteira: escolhido pela memória; o
  custo é uma consulta a mais (`intervalo_datas`) por página.

### 7.2 O que faríamos com mais budget
- **UI de verdade** (FastAPI + React/Plotly): mapa coroplético por município,
  gráficos interativos, filtros, autenticação.
- **Camada analítica** com DuckDB/Parquet e **atualização agendada** do banco vivo
  (o desafio pede "tempo real"); ingestão incremental por semana epidemiológica.
- **Métrica de UTI real** cruzando com a capacidade de leitos (CNES) e intervalos de
  confiança/suavização nas séries.
- **RAG mais forte**: boletins epidemiológicos oficiais + múltiplas fontes de
  notícias com deduplicação, e avaliação de relevância.
- **Observabilidade e avaliação**: tracing (LangSmith), testes de regressão de
  prompt, *backtesting* das métricas contra os painéis oficiais do Ministério.
- **Agente completo**: grafo LangGraph com planejamento e escolha de ferramentas,
  com os mesmos guardrails, servindo a própria página.
- **Entrega/DevOps**: Docker, CI no GitHub Actions rodando os testes com *gate* de
  cobertura.
