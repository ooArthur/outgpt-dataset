"""Gera avaliacao/perguntas_avaliacao.jsonl a partir de templates/avaliacao.txt (números vêm da ficha)."""
import re

from jinja2 import Environment, StrictUndefined

from common import RAIZ, escrever_jsonl, ler_doc, ler_jsonl, normaliza
from render_docs import contexto

TIPOS = {"simples": "simples", "numerica": "numerica", "multi-documento": "multi-documento",
         "versao": "versao_antiga_vs_nova", "sem_resposta": "sem_resposta", "fora_de_escopo": "fora_de_escopo"}
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")


def perguntas_treino():
    qs = set()
    for arq in ("qa/qa_treino.jsonl", "qa/qa_teste.jsonl"):
        for r in ler_jsonl(arq):
            for m in r["messages"]:
                if m["role"] == "user":
                    qs.add(normaliza(m["content"].split("PERGUNTA:")[-1]))
    return qs


def texto_fontes(fontes):
    partes = []
    for rel in fontes:
        if rel.endswith(".md"):
            partes.append(ler_doc(rel)[1])
        else:
            partes.append((RAIZ / rel).read_text(encoding="utf-8"))
    return "\n".join(partes)


def main():
    env = Environment(undefined=StrictUndefined)
    ctx = contexto()
    treino = perguntas_treino()
    itens, erros = [], []
    texto = (RAIZ / "templates" / "avaliacao.txt").read_text(encoding="utf-8")
    for bloco in re.split(r"\n\s*\n", texto.strip()):
        linhas = [l for l in bloco.splitlines() if l.strip() and not l.startswith("#")]
        if not linhas:
            continue
        reg = {}
        for l in linhas:
            k, _, v = l.partition(":")
            reg[k.strip()] = env.from_string(v.strip()).render(**ctx).strip()
        fontes = [d.strip() for d in reg.get("D", "").split(";") if d.strip()]
        for d in fontes:
            if not (RAIZ / d).exists():
                erros.append(f"fonte inexistente: {d}")
        if normaliza(reg["Q"]) in treino:
            erros.append(f"pergunta repetida do treino/teste: {reg['Q']}")
        if reg["T"] in ("simples", "numerica", "multi-documento", "versao") and "C" not in reg and fontes:
            base = texto_fontes(fontes)
            for n in NUM_RE.findall(reg["A"]):
                if n not in base:
                    erros.append(f"número {n!r} da resposta ausente nas fontes: {reg['Q'][:60]}")
        itens.append({"pergunta": reg["Q"], "resposta_esperada": reg["A"], "fonte_doc": fontes, "tipo": TIPOS[reg["T"]]})
    assert not erros, "\n".join(erros)
    assert len(itens) == 100, f"esperado 100 perguntas, há {len(itens)}"
    escrever_jsonl("avaliacao/perguntas_avaliacao.jsonl", itens)
    from collections import Counter
    print("avaliacao:", len(itens), dict(Counter(i["tipo"] for i in itens)))


if __name__ == "__main__":
    main()
