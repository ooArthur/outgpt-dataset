# OutGPT Enterprise — base de conhecimento sintética (Brisa Log)

> **Status: ✅ v1.1.** A versão entregue na Sprint 1 está na tag `sprint1-entrega`; o que mudou na v1.1 está em [“O que mudou na v1.1”](#o-que-mudou-na-v11) e no [`CHANGELOG.md`](CHANGELOG.md). Documentos, CSVs, catálogo de fatos, perguntas e respostas, avaliação, tickets e validação estão prontos; Documentos, CSVs, catálogo de fatos, perguntas e respostas, avaliação, tickets e validação estão prontos; `python validacao/validar.py` passa sem erros (ver [`validacao/relatorio.md`](validacao/relatorio.md)).

Base de conhecimento **100% fictícia** de uma empresa brasileira inventada, a **Brisa Logística e Distribuição S.A. (Brisa Log)**, criada para o projeto acadêmico de PLN **OutGPT Enterprise**: um assistente corporativo de onboarding e dúvidas internas (RH, financeiro, TI e compliance) sobre o LibreChat.

> ⚠️ **Tudo aqui é fictício.** Pessoas, CNPJ (`00.000.000/0001-00`), endereços, telefones e e-mails (`@brisalog.example`) foram inventados. Qualquer semelhança com a realidade é coincidência. Nada deve ser usado como informação ou aconselhamento real, inclusive jurídico.

## Para que serve

| Uso no projeto | Parte da base |
|---|---|
| **RAG** sobre documentos da empresa | `docs/` (Markdown com front matter, um tema por arquivo) |
| **Ajuste fino (QLoRA)** de um SLM de 1,5B a 3B | `qa/qa_treino.jsonl` (formato chat) |
| **Avaliação** do assistente | `qa/qa_teste.jsonl`, `avaliacao/perguntas_avaliacao.jsonl` |
| **Triagem de incidentes de TI** e sentimento | `tickets/tickets_ti.csv` |

## A empresa em resumo

Distribuidora e operadora logística de alimentos e bebidas para o varejo regional, fundada em 2009, com sede em Campinas/SP e centros de distribuição em Campinas/SP e Uberlândia/MG. Cerca de 140 colaboradores e faturamento líquido de cerca de R$ 85 milhões em 2025. Valores: *Cuidado com a cadeia, Palavra cumprida, Simplicidade, Aprender sempre*.

## Estrutura de pastas

```
outgpt-dataset/
├── ficha-mestra/               # empresa.yaml (fonte única da verdade) e acesso.yaml (matriz de perfis)
├── templates/                  # Jinja2 dos documentos (.md.j2), fatos (.fatos), avaliacao.txt e acesso.txt
├── docs/                       # 46 documentos renderizados (institucional, rh, financeiro, ti, comercial, compliance)
├── data/                       # funcionarios, financeiro_trimestral, orcamento_departamentos_2026, catalogo_servicos (CSV)
├── fatos/fatos.jsonl           # catálogo de fatos atômicos
├── qa/                         # qa_treino/qa_teste (chat) e qa_memorizacao_treino/teste (perguntas diretas sobre fatos rag)
├── avaliacao/                  # perguntas_avaliacao.jsonl, perguntas_acesso.jsonl, rodar_avaliacao.py e resultados/
├── tickets/tickets_ti.csv      # 500 tickets de TI (com dificuldade e categoria secundária)
├── export/                     # sft_*.jsonl: só `messages`, prontos para o treinador
├── rag/                        # chunks.jsonl, buscar.py (BM25), avaliar_recuperacao.py, ingest_pgvector.py (opcional)
├── treino/qlora_colab.ipynb    # QLoRA com Unsloth (Colab T4) -> GGUF -> Ollama
├── scripts/                    # build_all.py e uma etapa por script (gen_*, acesso.py, teste_*.py, baseline_triagem.py...)
└── validacao/                  # validar.py, relatorio.md e baseline_tickets.md
```

## Como foi gerada e como regenerar

Nenhum número é digitado à mão nos textos: tudo vem de `ficha-mestra/empresa.yaml`. O pipeline (seed fixa, sem rede e sem APIs pagas) é:

1. `gen_data.py` — gera os CSVs de `data/` a partir da ficha (quadro de pessoal, DRE, orçamento, catálogo).
2. `render_docs.py` — renderiza `templates/*/*.md.j2` com Jinja2, puxando valores da ficha e dos CSVs (`StrictUndefined`: variável inexistente quebra o build).
3. `gen_fatos.py` — junta fatos escritos à mão (`templates/fatos/*.fatos`, com respostas também geradas pela ficha) e fatos programáticos dos CSVs. **Cada fato escrito à mão carrega uma evidência que precisa existir no documento renderizado**, e os números do fato precisam aparecer na resposta; se não, o build falha.
4. `gen_qa.py` — gera de 3 a 5 formulações por fato (formal, informal, curta e ~5% com erro de digitação), pares `sem_resposta`, `fora_de_escopo` e `multi_turno`. Fatos `rag` só aparecem em `com_contexto`, com o trecho real do documento (e, às vezes, trechos distratores e a versão irmã revogada). A divisão treino/teste é **por `fato_id`** (85/15).
5. `gen_avaliacao.py` — 100 perguntas manuscritas (`templates/avaliacao.txt`), com números derivados da ficha e checagem contra repetição do treino/teste.
6. `gen_tickets.py` — 500 tickets sintéticos de TI com prioridade coerente com o SLA da ficha.
7. `validacao/validar.py` — valida tudo, escreve `validacao/relatorio.md` e atualiza a tabela de estatísticas abaixo.

```bash
pip install -r requirements.txt     # pyyaml e jinja2 (Python 3.10+)
python scripts/build_all.py         # regenera data/, docs/, fatos/, qa/, avaliacao/, tickets/, rag/, export/ e roda a validação
python validacao/validar.py         # só a validação (falha com código 1 se houver problema)
```

A saída é determinística: rodar o build duas vezes produz arquivos idênticos.

## Esquema dos arquivos

- **`docs/*/*.md`** — front matter YAML com `titulo`, `area`, `versao`, `vigencia`, `acesso` (`publico`, `gestores`, `rh_restrito`, `financeiro_restrito`), `responsavel` (+ `status`: `vigente`/`revogada`, e `substitui`/`substituido_por` nos pares de versão). Um tema por arquivo, 300 a 900 palavras, títulos claros para chunking. Todo documento termina com *"Documento fictício, criado para fins acadêmicos."* Há 4 pares de versão antiga (revogada) e nova: home office, reembolso, alçadas de aprovação e brindes.
- **`data/funcionarios.csv`** — `id, nome, cargo, departamento, gestor_id, unidade, data_admissao, ramal, email` (sem salário individual; todo `gestor_id` existe; só a CEO fica sem gestor).
- **`data/financeiro_trimestral.csv`** — 2024T1 a 2026T2: `receita_bruta, deducoes, receita_liquida, cmv, lucro_bruto, despesas_operacionais, ebitda, depreciacao_amortizacao, resultado_financeiro, ir_csll, resultado_liquido` (a aritmética fecha e a receita líquida de 2025 soma o valor da ficha).
- **`data/orcamento_departamentos_2026.csv`** — `departamento, trimestre, orcado, realizado, saldo, status` (realizado só até 2026T2).
- **`data/catalogo_servicos.csv`** — `codigo, servico, categoria, unidade_cobranca, preco_unitario_brl, disponibilidade, observacao`.
- **`fatos/fatos.jsonl`** — `fato_id, area, fato, fonte_doc, destino` (`finetuning` para fatos estáveis; `rag` para números, valores, preços e diretório), `sensibilidade` (igual ao `acesso` do documento) e, como apoio à geração: `perguntas, chave, resposta, evidencia`.
- **`qa/qa_treino.jsonl`, `qa/qa_teste.jsonl`** — formato chat do OutGPT:

  ```json
  {"messages": [
     {"role": "system", "content": "Você é o OutGPT, assistente interno da Brisa Log. ..."},
     {"role": "user", "content": "..."},
     {"role": "assistant", "content": "..."}],
   "meta": {"fato_id": "rh-ferias-01", "tipo": "direta", "area": "rh", "fonte_doc": "docs/rh/ferias.md", "estilo": "formal", "sensibilidade": "publico"}}
  ```

  Tipos (`meta.tipo`): `direta` (sem contexto; só fatos de ajuste fino), `com_contexto` (`CONTEXTO:\n<trechos com [Fonte: ...]>\n\nPERGUNTA: ...`; todos os fatos `rag`), `sem_resposta` (≈15%; resposta padrão *"Não encontrei essa informação nos documentos da empresa. Sugiro falar com <área>."*), `multi_turno` (≈5%; 2 a 3 turnos, com `meta.fato_ids`) e `fora_de_escopo` (≈3%). `estilo`: `formal`, `informal`, `curta` ou `erro_digitacao`.
- **`avaliacao/perguntas_avaliacao.jsonl`** — `pergunta, resposta_esperada, fonte_doc` (lista) e `tipo` (`simples`, `numerica`, `multi-documento`, `versao_antiga_vs_nova`, `sem_resposta`, `fora_de_escopo`). Nenhuma pergunta repete o treino ou o teste.
- **`tickets/tickets_ti.csv`** — `id, data, departamento_solicitante, assunto, descricao, categoria, fila, prioridade, tipo, sentimento` e (v1.1) `dificuldade, categoria_secundaria`. Categorias, filas, prioridades (P1 a P4, conforme o SLA: 4 h, 8 h, 3 dias úteis e 5 dias úteis) e sentimentos (`neutro`, `frustrado`, `urgente`, `positivo`) como na especificação do projeto. Linguagem variada: abreviações, mensagens curtas e longas, tom irritado em cerca de 15%.

## O que mudou na v1.1

| # | Mudança | Onde |
|---|---|---|
| A | Fim da abertura empilhada nas perguntas formais ("Preciso confirmar uma informação: Preciso falar com…") | `scripts/gen_qa.py`, regra nova no validador |
| B | 7 variantes de recusa (a original ≤ 30%) e respostas enriquecidas (abertura com o título do documento e fecho com contato da área), sem inventar números | `scripts/common.py`, `scripts/gen_qa.py` |
| C | Pares de **memorização**: perguntas diretas sobre fatos `rag` do split de treino, em arquivos separados | `scripts/gen_memorizacao.py`, `qa/qa_memorizacao_*.jsonl` |
| D | **Controle de acesso**: matriz de perfis, filtro determinístico, 20 itens de avaliação e testes | `ficha-mestra/acesso.yaml`, `scripts/acesso.py`, `avaliacao/perguntas_acesso.jsonl` |
| E | Tickets mais difíceis (21%: ambíguos, vagos, gírias) e baseline de triagem | `scripts/gen_tickets.py`, `scripts/baseline_triagem.py` |
| F | Exportação para treino, RAG BM25 de referência, runner de avaliação com Ollama e notebook QLoRA | `export/`, `rag/`, `avaliacao/rodar_avaliacao.py`, `treino/` |

Compatibilidade: nenhum arquivo, coluna, campo ou `fato_id` da v1.0 foi removido ou renomeado; só foram acrescentados. Números de antes e depois no [`CHANGELOG.md`](CHANGELOG.md).

## Experimentos

O trabalho compara seis cenários com o mesmo modelo base (**Qwen2.5 3B Instruct**, ajustado com QLoRA no `treino/qlora_colab.ipynb`):

| Cenário | Rótulo | Modelo | Dados de ajuste | RAG |
|---|---|---|---|---|
| A | `base` | Qwen2.5 3B Instruct | nenhum | não |
| B | `base_rag` | idem | nenhum | sim |
| C | `ft` | idem | `qa_treino` | não |
| D | `ft_rag` | idem | `qa_treino` | sim |
| E | `ft_memo` | idem | `qa_treino` + `qa_memorizacao_treino` | não |
| F | `ft_memo_rag` | idem | `qa_treino` + `qa_memorizacao_treino` | sim |

A, B, C e D são o mínimo exigido; E e F são o diferencial. Cada cenário é avaliado com `avaliacao/rodar_avaliacao.py` (veja “Avaliação”). Os comandos exatos estão lá.

## Memorização

`qa_treino.jsonl` ensina o modelo a **ler o contexto recuperado**: todo fato `rag` (números, preços, diretório) aparece só como `com_contexto`. Logo, o modelo ajustado **sem RAG** (cenário C) não conhece esses valores. Para medir quanto ele consegue memorizar sozinho, a v1.1 traz arquivos separados:

- `qa/qa_memorizacao_treino.jsonl`: perguntas **diretas** (sem `CONTEXTO:`) sobre fatos `rag`, com a resposta canônica do fato (sem abertura, fecho nem “Fonte”). Quatro formulações por fato.
- `qa/qa_memorizacao_teste.jsonl`: uma formulação **inédita** por fato (informal ou, se colidir, com erro de digitação), para testar memorização com mudança de redação.

Regras: só entram fatos do **split de treino** (os fatos do split de teste continuam inéditos, para medir generalização) e **nunca** fatos de documentos revogados (`*-v2025.md`): uma pergunta direta sobre “home office” ou “alçada”, sem contexto, não distingue versão antiga de nova, e treinar os dois valores criaria alvos contraditórios. A distribuição por área está em `validacao/relatorio.md` (o financeiro e o diretório pesam mais). `qa_treino.jsonl` e `qa_teste.jsonl` não foram alterados por isso, e o validador continua proibindo pergunta direta de fato `rag` neles.

## Controle de acesso

**Princípio:** o controle de acesso é responsabilidade da **plataforma** (filtro dos documentos *antes* do RAG), não do modelo. O modelo não sabe quem está perguntando; treiná-lo para “negar” seria frágil e burlável. A base entrega três coisas: a matriz de perfis, um filtro determinístico e testável, e um conjunto de avaliação.

Matriz (`ficha-mestra/acesso.yaml`):

| Perfil | `publico` | `gestores` | `rh_restrito` | `financeiro_restrito` |
|---|:-:|:-:|:-:|:-:|
| colaborador | ✅ | | | |
| gestor | ✅ | ✅ | | |
| rh | ✅ | ✅ | ✅ | |
| financeiro | ✅ | ✅ | | ✅ |
| diretoria | ✅ | ✅ | ✅ | ✅ |

Os quatro documentos restritos são `rh/faixas-salariais` (`rh_restrito`), `financeiro/resumo-dre` (`financeiro_restrito`), `financeiro/orcamento-departamentos` e `comercial/precos-e-descontos` (`gestores`). O nível dos CSVs é deduzido dos fatos que os citam e, quando não há fato, vem de `fontes_csv` na matriz (o teste confere as duas fontes).

- `scripts/acesso.py`: `acesso_da_fonte`, `pode_ver(perfil, fonte)`, `fontes_permitidas(perfil)` e `filtrar_trechos(perfil, trechos)`. O `rag/buscar.py` o aplica **antes** do ranking.
- `avaliacao/perguntas_acesso.jsonl`: 20 itens (10 `negar` e 10 `responder`), com 7 pares espelho (a mesma pergunta feita por um perfil sem permissão e por um com permissão), 4 itens sobre CSVs restritos e 3 perguntas públicas feitas por colaborador (para checar que o filtro não bloqueia demais). Campos: `pergunta, resposta_esperada, fonte_doc, tipo, perfil, comportamento`.
- `scripts/teste_acesso.py` (chamado pelo validador): `pode_ver` precisa ser falso quando o item pede `negar` e verdadeiro quando pede `responder`; a matriz cobre todos os níveis presentes nos documentos.
- `rag/relatorio_recuperacao.md` mostra por que o filtro é indispensável: sem ele, a recuperação entregaria o trecho restrito ao modelo.

Na integração com o LibreChat, o grupo precisa reproduzir esse filtro na camada de recuperação (por exemplo, a coluna `acesso` em `ingest_pgvector.py`); consulte a documentação oficial do LibreChat para os mecanismos de perfil e permissão da versão usada.

## Tickets: dificuldade e baseline

`tickets/tickets_ti.csv` ganhou duas colunas (ao final): `dificuldade` (`facil`/`dificil`) e `categoria_secundaria`. Dos 500 tickets, **105 (21%) são difíceis**, e foram trocados mantendo categoria, prioridade, sentimento, data e departamento do ticket original (a distribuição não mudou):

- **55 ambíguos (11%)**: o texto descreve dois problemas de categorias diferentes; `categoria` é a do primeiro problema citado, `categoria_secundaria` é a outra, e a prioridade segue o SLA da categoria principal;
- **25 muito curtos e vagos (5%)**, de 1 a 6 palavras (“não funciona”, “sistema fora”); o `assunto` ainda traz pistas da categoria;
- **25 com vocabulário informal pesado (5%)**: gírias, abreviações e erros de digitação.

**Baseline** (`python scripts/baseline_triagem.py`, requer scikit-learn; fora do `build_all.py`): TF-IDF de palavras e caracteres + regressão logística, divisão 80/20 estratificada por categoria e validação cruzada de 5 dobras. Grava `validacao/baseline_tickets.md` com acurácia e F1 macro por alvo (categoria, fila, prioridade, sentimento, tipo), separados por dificuldade, e a matriz de confusão da categoria. Na geração desta versão, a categoria ficou em ≈ 98% nos fáceis e ≈ 78% nos difíceis (validação cruzada); mesmo assim os dados continuam sintéticos, e o desempenho em tickets reais será menor.

**Misturar com tickets reais públicos.** Faça o download **manual** de uma amostra de [Tobi-Bueck/customer-support-tickets](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets) (no site do Hugging Face), **não copie para este repositório** e mapeie as colunas dela (assunto, texto, fila/tipo/prioridade) para o esquema deste CSV antes de misturar ou de avaliar. Atenção ao idioma: aquela base não é majoritariamente em português, então use-a como teste de robustez, não como substituta.

## Exportação para treino

`python scripts/exportar_treino.py` (já faz parte do build) grava em `export/` arquivos com **só a chave `messages`** (sem `meta`, para o treinador não reclamar de colunas extras), embaralhados com seed da ficha:

| Arquivo | Conteúdo | Cenários |
|---|---|---|
| `sft_treino_base.jsonl` | `qa_treino` | C, D |
| `sft_treino_memorizacao.jsonl` | `qa_treino` + `qa_memorizacao_treino` | E, F |
| `sft_teste.jsonl` | `qa_teste` (perda de validação) | todos |
| `sft_memorizacao_teste.jsonl` | `qa_memorizacao_teste` | E, F |

**Mistura com dados gerais em português** (opcional, para reduzir esquecimento): faça o download **manual** do [Canarim-Instruct-PTBR](https://huggingface.co/datasets/dominguesm/Canarim-Instruct-PTBR-Dataset) (arquivo `.jsonl` ou `.parquet`), converta e misture:

```bash
python scripts/converter_instrucoes.py canarim.parquet --saida geral_ptbr.jsonl --limite 3000
python scripts/exportar_treino.py --mistura geral_ptbr.jsonl --prop 0.2 --saida sft_treino_memorizacao_mix.jsonl
```

O conversor aceita colunas `instruction`/`input`/`output` (formato Alpaca); se não existirem, ele **lista as colunas encontradas e para**, sem adivinhar. `.parquet` exige `pandas` e `pyarrow` (`pip install -r requirements-opcional.txt`). `--prop` é a fração de exemplos gerais no arquivo final.

**Notebook de treino:** `treino/qlora_colab.ipynb` (gerado por `scripts/gerar_notebook.py`, validado com `nbformat.validate`) segue o notebook oficial de conversação do Unsloth, com `unsloth/Qwen2.5-3B-Instruct` em 4 bits (LoRA r=16, α=16, atenção + MLP), `max_seq_length=2048`, treino só nas respostas, 2 épocas, lr 2e-4, lote 2 × acumulação 4, exportação **GGUF q4_k_m**, `Modelfile` e `ollama create brisa-ft -f Modelfile`. Uma variável no topo (`CONJUNTO`) escolhe entre `sft_treino_base` e `sft_treino_memorizacao`. **O notebook não foi executado** (sem GPU aqui). A maior conversa do treino tem 599 palavras; o notebook conta os tokens antes de treinar e para se algo passar de 2048.

## RAG de referência

- `rag/chunks.jsonl`: 533 trechos (393 de documentos + 140 linhas do diretório), no **mesmo formato** que o modelo viu no treino (`[Fonte: ...]` e o texto da seção; “Diretório — …” para pessoas), com `chunk_id, fonte_doc, titulo, area, versao, vigencia, acesso, status, texto`. Gerado por `scripts/gen_chunks.py` reutilizando `Contextos.chunks`.
- `rag/buscar.py`: BM25 em Python puro (minúsculas, sem acentos, stopwords básicas). `buscar(pergunta, k=4, perfil="diretoria")` aplica o filtro de acesso **antes** do ranking e **rebaixa** trechos de documentos revogados (a menos que a pergunta fale de 2025 ou da regra antiga). `montar_prompt(pergunta, trechos)` devolve o `CONTEXTO: … PERGUNTA: …` do treino. Linha de comando: `python rag/buscar.py "pergunta" --perfil colaborador`.
- `rag/avaliar_recuperacao.py`: hit@1/3/5 por tipo nas perguntas de avaliação e de acesso; resultado em [`rag/relatorio_recuperacao.md`](rag/relatorio_recuperacao.md). Os números são de um **baseline lexical**: perguntas multi-documento e de versão antiga vs. nova são as mais difíceis.
- `rag/ingest_pgvector.py` (opcional): gera embeddings pelo Ollama (`/api/embed`, modelo multilíngue `bge-m3`; `embeddinggemma` também é multilíngue) e grava em Postgres com pgvector, com a coluna `acesso` para filtragem. A dimensão do vetor é descoberta em tempo de execução. **Não foi testado** (não havia Postgres aqui): trate como ponto de partida e revise. Requer `psycopg` (`requirements-opcional.txt`).

## Avaliação

`avaliacao/rodar_avaliacao.py` fala com o Ollama (`POST /api/chat`, `stream: false`, `temperature: 0`, só biblioteca padrão). **Os autores não rodaram um modelo real**; o avaliador foi testado com modelos falsos (`--simular oraculo|vazio|recusa`, via `scripts/teste_avaliacao.py`, que o validador executa).

```bash
# cenários A a F (ajuste o nome dos modelos no Ollama)
python avaliacao/rodar_avaliacao.py --modelo qwen2.5:3b-instruct --cenario base
python avaliacao/rodar_avaliacao.py --modelo qwen2.5:3b-instruct --cenario base_rag      # usa RAG BM25
python avaliacao/rodar_avaliacao.py --modelo brisa-ft      --cenario ft
python avaliacao/rodar_avaliacao.py --modelo brisa-ft      --cenario ft_rag
python avaliacao/rodar_avaliacao.py --modelo brisa-ft-memo --cenario ft_memo   --conjuntos avaliacao,acesso,memorizacao_teste
python avaliacao/rodar_avaliacao.py --modelo brisa-ft-memo --cenario ft_memo_rag --conjuntos avaliacao,acesso,memorizacao_teste
```

Conjuntos: `avaliacao` (100), `acesso` (20, perfil de cada item), `memorizacao_teste`, `qa_teste`. Saídas: `avaliacao/resultados/<cenario>.jsonl` (item a item) e `avaliacao/resultados/resumo.md` (todos os cenários). Sem LLM como juiz (o `--juiz` é um gancho desligado). Métricas por tipo:

| Tipo | Métricas |
|---|---|
| simples, numerica, multi-documento, versao_antiga_vs_nova, memorizacao | `acerto_numerico` (todos os números esperados aparecem; normaliza “R$ 2.000”, “2000”, “1,5”) e `cobertura_lexical` (palavras com ≥ 5 letras da resposta esperada presentes) |
| sem_resposta | `recusa_correta` (usa `MARCADORES_RECUSA`) e `alucinacao` (não recusou e inventou número) |
| fora_de_escopo | `recusa_correta` (usa `MARCADORES_FORA_ESCOPO`) |
| acesso | `negar`: recusa de acesso ou “não encontrei”, sem vazar os números do item espelho; `responder`: acerto numérico |

Métricas lexicais são só uma aproximação: revise algumas respostas à mão.

## Limitações

- **Dados sintéticos**: os textos foram escritos para este projeto e servem para provar a arquitetura (RAG, QLoRA, triagem), não para medir desempenho em linguagem real. Por isso a lista de bases públicas complementares abaixo.
- **Respostas curtas por fato**: cada fato tem uma resposta canônica; a v1.1 só varia a abertura e o fecho. A média ficou em ≈ 24 palavras por resposta e ≈ 37% de respostas distintas no treino (metas da v1.1: 26 palavras e 40%; ver `CHANGELOG.md`). As variações de pergunta vêm de regras, então a diversidade lexical é limitada.
- **Tickets sintéticos**: vêm de um banco de cenários; mesmo os “difíceis” repetem vocabulário e o baseline vai muito bem nos fáceis. Não imitam o ruído de tickets reais.
- **Recuperação BM25 como baseline**: é lexical e simples; perguntas que combinam vários documentos ou versões saem pior (veja `rag/relatorio_recuperacao.md`). Não há recuperação densa testada.
- **Nada de treino nem de avaliação com modelo real foi executado aqui**: o notebook QLoRA, o runner com Ollama e a ingestão em pgvector foram escritos e verificados estaticamente (ou com modelos falsos), não rodados em GPU, Ollama ou Postgres.
- **Controle de acesso** é testado no nível da base e do filtro; a integração com o LibreChat é responsabilidade do grupo.
- Informações restritas (faixas salariais, DRE) existem de propósito para testar controle de acesso; são tão fictícias quanto o resto.

## Estatísticas

<!-- STATS:START -->
| Item | Quantidade |
|---|---:|
| Documentos Markdown (`docs/`) | 46 (4 pares de versão antiga e nova) |
| Funcionários (`data/funcionarios.csv`) | 140 |
| Trimestres financeiros (2024T1–2026T2) | 10 |
| Linhas de orçamento 2026 | 28 |
| Serviços no catálogo | 22 |
| Fatos atômicos (`fatos/fatos.jsonl`) | 508 (131 finetuning, 377 rag) |
| Pares de QA (treino + teste) | 3114 (2631 + 483) |
| &nbsp;&nbsp;↳ `com_contexto` | 1956 |
| &nbsp;&nbsp;↳ `direta` | 450 |
| &nbsp;&nbsp;↳ `fora_de_escopo` | 94 |
| &nbsp;&nbsp;↳ `multi_turno` | 156 |
| &nbsp;&nbsp;↳ `sem_resposta` | 458 |
| Pares de memorização (`qa_memorizacao_*`) | 1489 (1180 + 309) |
| Perguntas de avaliação | 100 |
| Itens de avaliação de acesso | 20 (10 negar, 10 responder) |
| Tickets de TI | 500 (105 difíceis, 55 ambíguos) |
<!-- STATS:END -->

## Checklist de entrega

- [x] Estrutura do repositório, `requirements.txt`, licenças
- [x] Ficha-mestra completa (`ficha-mestra/empresa.yaml`)
- [x] CSVs de `data/` (funcionários, financeiro, orçamento, catálogo)
- [x] Motor de templates e 46 documentos (incluindo 4 pares de versão antiga e nova)
- [x] Catálogo de fatos (≥ 350)
- [x] Perguntas e respostas de treino e teste (≈ 3.000, divisão por `fato_id`)
- [x] 100 perguntas de avaliação
- [x] 500 tickets de TI
- [x] `validacao/validar.py` e relatório
- [x] Tabela de estatísticas final
- [x] v1.1: abertura formal corrigida, recusas variadas, memorização, controle de acesso, tickets difíceis + baseline
- [x] v1.1: exportação para treino, RAG BM25, runner de avaliação, notebook QLoRA, CHANGELOG
- [ ] (do grupo) treinar no Colab, rodar a avaliação com Ollama e integrar ao LibreChat

## Bases públicas complementares

- [EnterpriseRAG-Bench](https://huggingface.co/datasets/SJChen02/EnterpriseRAG-Bench)
- [GitLab Handbook](https://handbook.gitlab.com/handbook/)
- [Customer Support Tickets (Tobi-Bueck)](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets)
- [RagMixPTBR-Legal-Alpaca-2M](https://huggingface.co/datasets/cnmoro/RagMixPTBR-Legal-Alpaca-2M)
- [Canarim-Instruct-PTBR-Dataset](https://huggingface.co/datasets/dominguesm/Canarim-Instruct-PTBR-Dataset)
- [B2W Reviews](https://github.com/americanas-tech/b2w-reviews01)
- [FinQA (IBM)](https://huggingface.co/datasets/ibm/finqa)

## Licenças

- **Dados e textos** (`docs/`, `data/`, `fatos/`, `qa/`, `avaliacao/`, `tickets/`, `ficha-mestra/`): **CC BY 4.0**.
- **Código** (`scripts/`, `validacao/`, `templates/`): **MIT**.

Detalhes em [`LICENSE`](LICENSE).
