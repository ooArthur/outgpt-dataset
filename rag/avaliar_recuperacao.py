"""Mede a recuperação BM25 (hit@1/3/5) nas perguntas de avaliação e de acesso. Grava rag/relatorio_recuperacao.md.

Uso: python rag/avaliar_recuperacao.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from buscar import buscar  # noqa: E402

KS = (1, 3, 5)
TODAS_AS_FONTES = {"multi-documento", "versao_antiga_vs_nova"}


def ler(caminho):
    return [json.loads(l) for l in (RAIZ / caminho).read_text(encoding="utf-8").splitlines() if l.strip()]


def acertou(tipo, esperadas, recuperadas):
    return set(esperadas) <= set(recuperadas) if tipo in TODAS_AS_FONTES else bool(set(esperadas) & set(recuperadas))


def main():
    hits, totais = defaultdict(lambda: defaultdict(int)), defaultdict(int)
    for it in ler("avaliacao/perguntas_avaliacao.jsonl"):
        if not it["fonte_doc"]:
            continue  # sem_resposta e fora_de_escopo não têm fonte esperada
        res = buscar(it["pergunta"], k=max(KS), perfil="diretoria")
        totais[it["tipo"]] += 1
        for k in KS:
            hits[it["tipo"]][k] += acertou(it["tipo"], it["fonte_doc"], [r["fonte_doc"] for r in res[:k]])
    acesso = {"responder": [0, defaultdict(int)], "negar": [0, 0, 0]}  # negar: n, bloqueios corretos, vazariam sem filtro
    for it in ler("avaliacao/perguntas_acesso.jsonl"):
        fontes = it["fonte_doc"]
        if it["comportamento"] == "responder":
            res = buscar(it["pergunta"], k=max(KS), perfil=it["perfil"])
            acesso["responder"][0] += 1
            for k in KS:
                acesso["responder"][1][k] += acertou("simples", fontes, [r["fonte_doc"] for r in res[:k]])
        else:
            com = buscar(it["pergunta"], k=5, perfil=it["perfil"])
            sem = buscar(it["pergunta"], k=5, perfil=it["perfil"], filtrar=False)
            acesso["negar"][0] += 1
            acesso["negar"][1] += not (set(fontes) & {r["fonte_doc"] for r in com})
            acesso["negar"][2] += bool(set(fontes) & {r["fonte_doc"] for r in sem})
    linhas = ["# Relatório de recuperação (BM25)\n",
              "Recuperação lexical em Python puro (`rag/buscar.py`) sobre `rag/chunks.jsonl`, com filtro de acesso antes do ranking e "
              "rebaixamento de documentos revogados. É um **baseline**: a recuperação densa (embeddings) deve ser comparada a ele.\n",
              "## Perguntas de avaliação (perfil diretoria)\n",
              "`hit@k` = alguma fonte esperada entre os k primeiros (para `multi-documento` e `versao_antiga_vs_nova`, **todas** as fontes esperadas).\n",
              "| Tipo | Perguntas | hit@1 | hit@3 | hit@5 |", "|---|---:|---:|---:|---:|"]
    soma = defaultdict(int)
    for tipo in sorted(totais):
        n = totais[tipo]
        linhas.append(f"| {tipo} | {n} | " + " | ".join(f"{100 * hits[tipo][k] / n:.0f}%" for k in KS) + " |")
        soma["n"] += n
        for k in KS:
            soma[k] += hits[tipo][k]
    linhas.append(f"| **todas com fonte** | {soma['n']} | " + " | ".join(f"{100 * soma[k] / soma['n']:.0f}%" for k in KS) + " |")
    nr, hr = acesso["responder"]
    linhas += ["\n_sem_resposta_ e _fora_de_escopo_ não têm fonte esperada e ficam de fora.\n", "## Perguntas de acesso (perfil de cada item)\n",
               "| Comportamento | Itens | Resultado |", "|---|---:|---|",
               f"| responder (hit@1 / hit@3 / hit@5) | {nr} | " + " / ".join(f"{100 * hr[k] / nr:.0f}%" for k in KS) + " |",
               f"| negar: fonte restrita NÃO aparece no top-5 com filtro | {acesso['negar'][0]} | {acesso['negar'][1]}/{acesso['negar'][0]} |",
               f"| negar: fonte restrita APARECERIA no top-5 sem filtro | {acesso['negar'][0]} | {acesso['negar'][2]}/{acesso['negar'][0]} |",
               "\nA última linha mostra por que o filtro é indispensável: sem ele, a recuperação entregaria o trecho restrito ao modelo."]
    destino = RAIZ / "rag" / "relatorio_recuperacao.md"
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print("\n".join(linhas))


if __name__ == "__main__":
    main()
