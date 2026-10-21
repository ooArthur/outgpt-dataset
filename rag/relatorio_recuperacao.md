# Relatório de recuperação (BM25)

Recuperação lexical em Python puro (`rag/buscar.py`) sobre `rag/chunks.jsonl`, com filtro de acesso antes do ranking e rebaixamento de documentos revogados. É um **baseline**: a recuperação densa (embeddings) deve ser comparada a ele.

## Perguntas de avaliação (perfil diretoria)

`hit@k` = alguma fonte esperada entre os k primeiros (para `multi-documento` e `versao_antiga_vs_nova`, **todas** as fontes esperadas).

| Tipo | Perguntas | hit@1 | hit@3 | hit@5 |
|---|---:|---:|---:|---:|
| multi-documento | 15 | 7% | 20% | 40% |
| numerica | 25 | 60% | 88% | 96% |
| simples | 30 | 67% | 83% | 93% |
| versao_antiga_vs_nova | 12 | 25% | 42% | 58% |
| **todas com fonte** | 82 | 48% | 67% | 79% |

_sem_resposta_ e _fora_de_escopo_ não têm fonte esperada e ficam de fora.

## Perguntas de acesso (perfil de cada item)

| Comportamento | Itens | Resultado |
|---|---:|---|
| responder (hit@1 / hit@3 / hit@5) | 10 | 50% / 80% / 80% |
| negar: fonte restrita NÃO aparece no top-5 com filtro | 10 | 10/10 |
| negar: fonte restrita APARECERIA no top-5 sem filtro | 10 | 6/10 |

A última linha mostra por que o filtro é indispensável: sem ele, a recuperação entregaria o trecho restrito ao modelo.
