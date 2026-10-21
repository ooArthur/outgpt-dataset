# OutGPT Enterprise — base de conhecimento sintética (Brisa Log)

> **Status: ✅ Sprint 1 concluída.** Documentos, CSVs, catálogo de fatos, perguntas e respostas, avaliação, tickets e validação estão prontos; `python validacao/validar.py` passa sem erros (ver [`validacao/relatorio.md`](validacao/relatorio.md)).

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
├── ficha-mestra/empresa.yaml   # fonte única da verdade (fatos e números)
├── templates/                  # templates Jinja2 dos documentos (.md.j2), fatos (.fatos) e avaliação (avaliacao.txt)
├── docs/                       # documentos renderizados (institucional, rh, financeiro, ti, comercial, compliance)
├── data/                       # funcionarios, financeiro_trimestral, orcamento_departamentos_2026, catalogo_servicos (CSV)
├── fatos/fatos.jsonl           # catálogo de fatos atômicos
├── qa/                         # qa_treino.jsonl e qa_teste.jsonl (formato chat)
├── avaliacao/                  # perguntas_avaliacao.jsonl
├── tickets/tickets_ti.csv      # 500 tickets de TI
├── scripts/                    # build_all.py e uma etapa por script
└── validacao/                  # validar.py e relatorio.md
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
python scripts/build_all.py         # regenera data/, docs/, fatos/, qa/, avaliacao/, tickets/ e roda a validação
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
- **`tickets/tickets_ti.csv`** — `id, data, departamento_solicitante, assunto, descricao, categoria, fila, prioridade, tipo, sentimento`. Categorias, filas, prioridades (P1 a P4, conforme o SLA: 4 h, 8 h, 3 dias úteis e 5 dias úteis) e sentimentos (`neutro`, `frustrado`, `urgente`, `positivo`) como na especificação do projeto. Linguagem variada: abreviações, mensagens curtas e longas, tom irritado em cerca de 15%.

## Limitações conhecidas

- Os textos são sintéticos e escritos para este projeto: servem para provar a arquitetura (RAG, QLoRA, triagem), não para medir desempenho em linguagem real. Por isso a lista de bases públicas complementares abaixo.
- As respostas dos pares de QA são curtas e padronizadas por fato; as variações de pergunta são geradas por regras (formal, informal, curta, erro de digitação), então a diversidade lexical é limitada.
- Os tickets vêm de um banco de cenários com variações de linguagem; as classes têm sobreposição natural, mas não imitam o ruído de tickets reais.
- Algumas informações de acesso restrito (faixas salariais, DRE) existem de propósito para testar controle de acesso por `sensibilidade`; são tão fictícias quanto o resto.

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
| Tickets de TI | 500 |
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
