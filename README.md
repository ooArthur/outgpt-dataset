# OutGPT Enterprise — base de conhecimento sintética (Brisa Log)

> **Status: 🚧 em construção (Sprint 1).** A ficha-mestra, os CSVs e os primeiros documentos já estão publicados; catálogo de fatos, perguntas e respostas, avaliação, tickets e validação estão sendo adicionados.

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
├── templates/                  # templates Jinja2 (.md.j2) dos documentos, por área
├── docs/                       # documentos renderizados (institucional, rh, financeiro, ti, comercial, compliance)
├── data/                       # funcionarios, financeiro_trimestral, orcamento_departamentos_2026, catalogo_servicos (CSV)
├── fatos/fatos.jsonl           # catálogo de fatos atômicos            (em construção)
├── qa/                         # qa_treino.jsonl e qa_teste.jsonl      (em construção)
├── avaliacao/                  # perguntas_avaliacao.jsonl             (em construção)
├── tickets/tickets_ti.csv      # tickets de TI                         (em construção)
├── scripts/                    # build_all.py e uma etapa por script
└── validacao/                  # validar.py e relatorio.md             (em construção)
```

## Como foi gerada e como regenerar

Nenhum número é digitado à mão nos textos: tudo vem de `ficha-mestra/empresa.yaml`. Os CSVs são gerados por `scripts/gen_data.py` (seed fixa) e os documentos são renderizados por Jinja2 a partir de `templates/`, puxando valores da ficha e dos CSVs. Assim, alterar um valor na ficha atualiza todos os documentos de forma coerente.

```bash
pip install -r requirements.txt     # pyyaml e jinja2 (Python 3.10+)
python scripts/build_all.py         # regenera data/ e docs/ (e, quando prontos, fatos, QA, avaliação e tickets)
```

## Esquema dos arquivos prontos

- **`docs/*/*.md`** — front matter YAML com `titulo`, `area`, `versao`, `vigencia`, `acesso` (`publico`, `gestores`, `rh_restrito`, `financeiro_restrito`), `responsavel` (+ `status`). Todo documento termina com a linha *"Documento fictício, criado para fins acadêmicos."*
- **`data/funcionarios.csv`** — `id, nome, cargo, departamento, gestor_id, unidade, data_admissao, ramal, email` (sem salário individual; todo `gestor_id` existe).
- **`data/financeiro_trimestral.csv`** — 2024T1 a 2026T2: receita bruta, deduções, receita líquida, CMV, lucro bruto, despesas operacionais, EBITDA, depreciação/amortização, resultado financeiro, IR/CSLL e resultado líquido (a aritmética fecha; a receita líquida de 2025 soma o valor da ficha).
- **`data/orcamento_departamentos_2026.csv`** — orçado, realizado e saldo por departamento e trimestre (realizado só até 2026T2).
- **`data/catalogo_servicos.csv`** — código, serviço, categoria, unidade de cobrança, preço, disponibilidade e observação.

## Checklist de entrega

- [x] Estrutura do repositório, `requirements.txt`, licenças
- [x] Ficha-mestra completa (`ficha-mestra/empresa.yaml`)
- [x] CSVs de `data/` (funcionários, financeiro, orçamento, catálogo)
- [x] Motor de templates + 8 documentos de amostra (um por área, incluindo uma política com versão antiga e nova)
- [x] 46 documentos (incluindo 4 pares de versão antiga e nova)
- [ ] Catálogo de fatos (≥ 350)
- [ ] Perguntas e respostas de treino e teste (alvo 3.000)
- [ ] 100 perguntas de avaliação
- [ ] 500 tickets de TI
- [ ] `validacao/validar.py` e relatório
- [ ] Tabela de estatísticas final

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
