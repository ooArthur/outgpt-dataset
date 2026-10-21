# Relatório de validação
Gerado por `validacao/validar.py`. **Status: ✅ APROVADO** — 0 erro(s), 0 aviso(s).
## Verificações
- Documentos: front matter completo, sem marcação `{{ }}`, 300 a 900 palavras, rodapé fictício, pares de versão.- Financeiro: aritmética de todos os trimestres e receita líquida de 2025 igual à ficha.- Funcionários: todo `gestor_id` existe; e-mails no domínio fictício; headcount igual ao da ficha.- JSONL válidos; sem perguntas duplicadas; nenhum `fato_id` no treino e no teste; todo `fonte_doc` existe.- Perguntas de fatos `rag` aparecem só como `com_contexto`; avaliação sem repetir treino/teste; tickets coerentes com o SLA; sem arquivos > 5 MB nem segredos.
## Contagens por arquivo
| Arquivo | Tamanho |
|---|---:|
| avaliacao/perguntas_avaliacao.jsonl | 31.8 KB |
| fatos/fatos.jsonl | 325.1 KB |
| qa/qa_teste.jsonl | 639.9 KB |
| qa/qa_treino.jsonl | 3664.0 KB |
| data/catalogo_servicos.csv | 2.7 KB |
| data/financeiro_trimestral.csv | 1.1 KB |
| data/funcionarios.csv | 18.1 KB |
| data/orcamento_departamentos_2026.csv | 1.4 KB |
| tickets/tickets_ti.csv | 142.5 KB |

- `docs/`: **46** documentos (306–712 palavras; média 376).
### Documentos por área
| Área | Documentos |
|---|---:|
| comercial | 3 |
| compliance | 6 |
| financeiro | 10 |
| institucional | 6 |
| rh | 13 |
| ti | 8 |

### CSVs (linhas)
| Arquivo | Linhas |
|---|---:|
| funcionarios | 140 |
| financeiro_trimestral | 10 |
| orcamento_departamentos_2026 | 28 |
| catalogo_servicos | 22 |

### Fatos
Total: **508**

| Destino | Fatos |
|---|---:|
| finetuning | 131 |
| rag | 377 |

| Área | Fatos |
|---|---:|
| comercial | 63 |
| compliance | 24 |
| financeiro | 171 |
| institucional | 136 |
| rh | 69 |
| ti | 45 |

| Sensibilidade | Fatos |
|---|---:|
| publico | 374 |
| gestores | 43 |
| financeiro_restrito | 86 |
| rh_restrito | 5 |

### Perguntas e respostas
Total: **3114** (treino 2631, teste 483); fatos distintos: treino 887, teste 173; formulações por fato (direta/com_contexto): 4.74.

| Tipo | Treino | Teste | Total |
|---|---:|---:|---:|
| com_contexto | 1673 | 283 | 1956 |
| direta | 375 | 75 | 450 |
| fora_de_escopo | 80 | 14 | 94 |
| multi_turno | 128 | 28 | 156 |
| sem_resposta | 375 | 83 | 458 |

### Avaliação
| Tipo | Perguntas |
|---|---:|
| simples | 30 |
| numerica | 25 |
| multi-documento | 15 |
| versao_antiga_vs_nova | 12 |
| sem_resposta | 10 |
| fora_de_escopo | 8 |

### Tickets de TI
| Categoria | Tickets |
|---|---:|
| Sistemas Internos | 87 |
| Segurança | 60 |
| Impressão | 49 |
| Rede e VPN | 67 |
| Acesso e Senhas | 62 |
| Hardware | 71 |
| E-mail e Colaboração | 58 |
| Software e Licenças | 46 |

| Prioridade | Tickets |
|---|---:|
| P1 | 41 |
| P2 | 81 |
| P3 | 249 |
| P4 | 129 |

| Sentimento | Tickets |
|---|---:|
| neutro | 298 |
| urgente | 54 |
| positivo | 63 |
| frustrado | 85 |

| Fila | Tickets |
|---|---:|
| Sistemas | 79 |
| Segurança | 65 |
| N1 | 254 |
| Infraestrutura | 62 |
| N2 | 40 |

| Tipo | Tickets |
|---|---:|
| incidente | 364 |
| requisição | 136 |
