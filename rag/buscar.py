"""RAG de referência: recuperação BM25 em Python puro, com filtro de acesso aplicado ANTES do ranking.

Uso em código:
    from buscar import buscar, montar_prompt
    trechos = buscar("Quantos dias de home office posso fazer?", k=4, perfil="colaborador")
    prompt_do_usuario = montar_prompt("Quantos dias de home office posso fazer?", trechos)

Uso na linha de comando:
    python rag/buscar.py "pergunta" [--k 4] [--perfil colaborador]
"""
import argparse
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
from acesso import pode_ver  # noqa: E402
from gen_qa import montar_contexto  # noqa: E402

CHUNKS = RAIZ / "rag" / "chunks.jsonl"
STOPWORDS = set("""a o as os um uma uns umas de da do das dos em no na nos nas por para pra com sem sobre ate e ou mas que se ao aos
 qual quais quanto quantos quantas quem como onde quando eu voce vc meu minha meus minhas seu sua nosso nossa ele ela eles elas
 ser sao foi e esta estao tem ha pode posso preciso favor mais menos muito entre ja so tambem isso essa esse esta este
 uso usar existe existem fazer faz""".split())
PERGUNTA_SOBRE_VERSAO_ANTIGA = re.compile(r"2025|antig|anterior|revogad|passad|velh|antes de 2026|mudou|mudanc|diferenc|ainda vale", re.I)
K1, B = 1.5, 0.75
FATOR_REVOGADO = 0.4  # chunks de documentos revogados só competem em pé de igualdade quando a pergunta fala da regra antiga


def normalizar(txt):
    return unicodedata.normalize("NFKD", txt.lower()).encode("ascii", "ignore").decode()


def tokenizar(txt):
    toks = []
    for t in re.findall(r"[a-z0-9]+", normalizar(txt)):
        if t in STOPWORDS:
            continue
        toks.append(t[:-1] if len(t) > 4 and t.endswith("s") else t)
    return toks


@lru_cache(maxsize=1)
def indice():
    chunks = [json.loads(l) for l in CHUNKS.read_text(encoding="utf-8").splitlines() if l.strip()]
    docs = [Counter(tokenizar(c["titulo"] + " " + c["titulo"] + " " + c["texto"])) for c in chunks]
    tam = [sum(d.values()) for d in docs]
    df = Counter(t for d in docs for t in d)
    n = len(chunks)
    return {"chunks": chunks, "docs": docs, "tam": tam, "media": sum(tam) / n, "n": n,
            "idf": {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}}


@lru_cache(maxsize=None)
def _pode(perfil, fonte):
    return pode_ver(perfil, fonte)


def buscar(pergunta, k=4, perfil="diretoria", filtrar=True):
    """Top-k chunks por BM25. O filtro de acesso (scripts/acesso.py) roda antes do ranking."""
    ix = indice()
    consulta = tokenizar(pergunta)
    antiga = bool(PERGUNTA_SOBRE_VERSAO_ANTIGA.search(pergunta))
    pontuados = []
    for i, c in enumerate(ix["chunks"]):
        if filtrar and not _pode(perfil, c["fonte_doc"]):
            continue
        d, norma = ix["docs"][i], 1 - B + B * ix["tam"][i] / ix["media"]
        score = sum(ix["idf"].get(t, 0.0) * d[t] * (K1 + 1) / (d[t] + K1 * norma) for t in consulta if t in d)
        if c["status"] == "revogada" and not antiga:
            score *= FATOR_REVOGADO
        if score > 0:
            pontuados.append((score, i))
    pontuados.sort(key=lambda x: (-x[0], x[1]))
    return [{**ix["chunks"][i], "score": round(s, 4)} for s, i in pontuados[:k]]


def montar_prompt(pergunta, trechos):
    """Mesmo formato visto no treino: CONTEXTO: [Fonte: ...] ... PERGUNTA: ..."""
    return montar_contexto([(t["fonte_doc"], t["texto"]) for t in trechos], pergunta)


def main():
    ap = argparse.ArgumentParser(description="Busca BM25 nos documentos da Brisa Log (referência)")
    ap.add_argument("pergunta")
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--perfil", default="diretoria", help="colaborador, gestor, rh, financeiro ou diretoria")
    args = ap.parse_args()
    for t in buscar(args.pergunta, args.k, args.perfil):
        print(f"{t['score']:7.3f}  {t['fonte_doc']}  [{t['chunk_id']}]  {t['texto'][:90].replace(chr(10), ' ')}...")


if __name__ == "__main__":
    main()
