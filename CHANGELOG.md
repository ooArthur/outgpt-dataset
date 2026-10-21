# Changelog

## v1.1 — melhorias pós-Sprint 1

Base: tag `sprint1-entrega` (commit `068e6ef`). Nenhum arquivo, coluna, campo ou `fato_id` da v1.0 foi removido ou renomeado.

### Métricas antes e depois (qa_treino.jsonl)

| Métrica | v1.0 | v1.1 | Meta | Situação |
|---|---:|---:|---:|---|
| Pares de treino / teste | 2.631 / 483 | 2.631 / 483 | — | iguais (o dataset não encolheu) |
| Pares com abertura conversacional empilhada | 55 (47 treino + 8 teste) | 0 | 0 | ✅ |
| Palavras por resposta (média) | 20,8 | 23,7 | ≥ 26 | ⚠️ não atingida |
| Respostas distintas / total | 665 (25%) | 985 (37,4%) | ≥ 40% | ⚠️ não atingida |
| Maior repetição de uma mesma resposta | 233 | 63 | ≤ 90 | ✅ |
| Recusa original entre as recusas | 100% | 26% (7 variantes) | ≤ 30% | ✅ |
| Números alterados ou novos em respostas de fatos | 0 | 0 (validado) | 0 | ✅ |

As duas metas de diversidade ficaram abaixo: cada fato tem uma resposta canônica e a abertura com título (só documentos vigentes, sem dígitos no título e sem “(Fonte: …)” na resposta) só se aplica a ≈ 7% dos pares; o fecho com contato, a 15% dos pares de documentos. Subir mais exigiria inventar conteúdo ou ignorar as regras de segurança da Parte B. O validador mostra a meta como nota no relatório, sem reprovar.

### Novos arquivos e contagens

| Item | Quantidade |
|---|---:|
| `qa_memorizacao_treino.jsonl` / `qa_memorizacao_teste.jsonl` | 1.180 / 309 pares (318 fatos `rag` do split de treino; 9 sem formulação inédita para o teste) |
| `avaliacao/perguntas_acesso.jsonl` | 20 itens (10 negar, 10 responder, 7 pares espelho, 4 sobre CSVs restritos, 3 públicas) |
| `tickets_ti.csv` difíceis | 105 (21%): 55 ambíguos, 25 muito curtos, 25 com gírias |
| `rag/chunks.jsonl` | 533 trechos (393 de documentos + 140 do diretório) |
| `export/` | 4 arquivos `messages` (3,2 MB a 3,9 MB os de treino) |
| `treino/qlora_colab.ipynb` | 25 células, validado com `nbformat.validate` |

### Resultados medidos nesta versão

- **Baseline de triagem** (`validacao/baseline_tickets.md`, validação cruzada de 5 dobras): categoria ≈ 98,5% nos tickets fáceis e ≈ 78,1% nos difíceis; nos ambíguos ≈ 61,8% (o alvo é a categoria do primeiro problema citado). Os fáceis continuam muito fáceis por serem sintéticos.
- **Recuperação BM25** (`rag/relatorio_recuperacao.md`, perguntas com fonte): hit@1 48%, hit@3 67%, hit@5 79%. `numerica` 60/88/96%, `simples` 67/83/93%, `versao_antiga_vs_nova` 25/42/58%, `multi-documento` 7/20/40%. Nas perguntas de acesso, o filtro bloqueou a fonte restrita nos 10 itens `negar`; sem o filtro, 6 dos 10 a entregariam.

### Decisões e desvios

- **Parte A:** a regra do validador também pega “Posso/Pode/Tenho…” depois de um prefixo, não só “Preciso…” (55 pares, não 11). Em vez de apenas remover o prefixo, a pergunta em primeira pessoa ganha um sufixo de cortesia (“, por favor?”, “, se possível?”…), escolhido pelo índice do prefixo descartado. Assim a pergunta continua distinta, não cai na deduplicação e o resto do dataset não mudou (contagem total idêntica; só as 56 linhas afetadas). Uma pergunta fora de escopo com dois `:` (“Grande Sertão: Veredas”) foi reescrita sem o `:`.
- **Parte B:** o enriquecimento da resposta usa um `random.Random(seed + 5)` próprio e sempre sorteia, para o resultado de um par não depender dos outros. A abertura “De acordo com …” não é aplicada quando a resposta já termina com “(Fonte: …)” (repetiria o título) nem em fatos de CSV; o fecho de contato não é aplicado a fatos do diretório (o contato “institucional” seria o RH). A lista de primeiras palavras seguras foi ampliada com artigos, preposições e alguns verbos/substantivos comuns (Você, Use, Abra, Chamados…), nunca nomes próprios. Três variantes de recusa têm uma segunda frase cordial.
- **Parte C:** o teste de memorização usa `informal(perguntas[1])` e, se colidir com qualquer pergunta existente (inclusive as de `templates/avaliacao.txt`), a versão com erro de digitação (97 dos 309 pares).
- **Parte D:** CSVs que não são fonte de nenhum fato (financeiro, orçamento, catálogo) têm o nível em `fontes_csv` de `acesso.yaml`; para os que têm fatos, o nível vem dos fatos e o teste confere a concordância. O item de avaliação que a especificação sugeria como exemplo (mensagem personalizada) usa a `mensagem_negado` padrão, com o e-mail da área dona do dado.
- **Parte E:** os 105 tickets difíceis **substituem** tickets existentes de mesma categoria, prioridade, sentimento, data e departamento, por isso as distribuições não mudaram e os 395 restantes são idênticos à v1.0. A refatoração de `gen_tickets.py` (função `compor`) foi verificada por diff: o CSV gerado antes das mudanças era byte a byte igual ao da v1.0.
- **Parte F:** a instalação e a estrutura de treino do notebook seguem o notebook oficial de conversação do Unsloth (Llama 3.2 1B/3B). Os marcadores de `train_on_responses_only` para o Qwen2.5 (`<|im_start|>user\n` / `<|im_start|>assistant\n`) **não foram confirmados na documentação**; o notebook confere o template antes de treinar e imprime os tokens treináveis de um exemplo. O `TEMPLATE` do `Modelfile` é o ChatML padrão e deve ser comparado com `ollama show --modelfile`. O modelo de embedding do `ingest_pgvector.py` é o `bge-m3` (multilíngue, confirmado na biblioteca do Ollama).

### Pendências

- Treinar no Colab, avaliar com o Ollama e integrar ao LibreChat (nada disso foi executado aqui: sem GPU, sem Ollama, sem Postgres).
- Metas de diversidade de resposta (26 palavras, 40% distintas) abaixo do alvo; ver acima.
- `rag/ingest_pgvector.py` não foi testado contra um Postgres real.

## v1.0 — Sprint 1 (tag `sprint1-entrega`)

Ficha-mestra, 46 documentos, 4 CSVs, 508 fatos, 3.114 pares de QA, 100 perguntas de avaliação, 500 tickets de TI e validador.
