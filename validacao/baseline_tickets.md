# Baseline de triagem de tickets de TI

TF-IDF (palavras 1-2 gramas + caracteres 2-5) + regressão logística, `scripts/baseline_triagem.py`. Divisão 80/20 estratificada por categoria (seed 20260420): 400 treino, 100 teste (19 difíceis e 81 fáceis no teste).

## Divisão 80/20: acurácia e F1 macro (%)

| Alvo | Acurácia (todos) | F1 macro (todos) | Acurácia fácil | F1 fácil | Acurácia difícil | F1 difícil |
|---|---:|---:|---:|---:|---:|---:|
| categoria | 95.0 | 95.1 | 98.8 | 98.8 | 78.9 | 81.2 |
| fila | 95.0 | 94.2 | 97.5 | 96.2 | 84.2 | 83.1 |
| prioridade | 94.0 | 88.7 | 93.8 | 89.8 | 94.7 | 65.5 |
| sentimento | 85.0 | 81.9 | 88.9 | 86.0 | 68.4 | 50.2 |
| tipo | 98.0 | 97.4 | 97.5 | 96.8 | 100.0 | 100.0 |

## Validação cruzada (5 dobras estratificadas por categoria, predições fora da dobra)

Com só ~100 tickets de teste, a diferença fácil x difícil é ruidosa; a validação cruzada usa os 500 tickets.

| Alvo | Acurácia fácil | F1 fácil | Acurácia difícil | F1 difícil |
|---|---:|---:|---:|---:|
| categoria | 98.5 | 98.6 | 78.1 | 77.7 |
| fila | 95.4 | 95.4 | 82.9 | 81.3 |
| prioridade | 91.4 | 89.4 | 76.2 | 68.3 |
| sentimento | 86.8 | 80.5 | 79.0 | 69.0 |
| tipo | 99.2 | 99.0 | 91.4 | 89.4 |

- Categoria nos tickets **ambíguos** (duas categorias, n=55): acurácia 61.8% (o alvo é a categoria do primeiro problema citado).
- Categoria nos tickets **muito curtos** (≤ 6 palavras, n=29): acurácia 96.6%.

## Matriz de confusão da categoria (divisão 80/20; linhas = real, colunas = previsto)

| real \ previsto | Acesso e Senhas | E-mail e Colaboração | Hardware | Impressão | Rede e VPN | Segurança | Sistemas Internos | Software e Licenças |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Acesso e Senhas | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| E-mail e Colaboração | 0 | 12 | 0 | 0 | 0 | 0 | 0 | 0 |
| Hardware | 0 | 0 | 14 | 0 | 0 | 0 | 0 | 0 |
| Impressão | 0 | 1 | 0 | 9 | 0 | 0 | 0 | 0 |
| Rede e VPN | 1 | 0 | 0 | 0 | 12 | 0 | 0 | 0 |
| Segurança | 1 | 0 | 0 | 0 | 0 | 10 | 1 | 0 |
| Sistemas Internos | 1 | 0 | 0 | 0 | 0 | 0 | 17 | 0 |
| Software e Licenças | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 9 |

> Dados sintéticos gerados por banco de cenários: o baseline tende a ir muito bem mesmo no conjunto difícil, porque o vocabulário dos cenários se repete. Não use estes números como estimativa de desempenho em tickets reais.
