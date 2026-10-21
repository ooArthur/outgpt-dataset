"""Gera avaliacao/perguntas_acesso.jsonl (20 itens) a partir de templates/acesso.txt."""
import re
from collections import Counter

from jinja2 import Environment, StrictUndefined

from acesso import mensagem_negado
from common import AREAS_SUG, RAIZ, escrever_jsonl, ler_doc, ler_jsonl, normaliza
from gen_avaliacao import perguntas_treino
from render_docs import contexto

NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")


def main():
    ctx = contexto()
    ctx["negado"] = lambda area: mensagem_negado(AREAS_SUG[area])
    env = Environment(undefined=StrictUndefined)
    proibidas = perguntas_treino() | {normaliza(r["pergunta"]) for r in ler_jsonl("avaliacao/perguntas_avaliacao.jsonl")}
    itens, erros = [], []
    for bloco in re.split(r"\n\s*\n", (RAIZ / "templates" / "acesso.txt").read_text(encoding="utf-8").strip()):
        linhas = [l for l in bloco.splitlines() if l.strip() and not l.startswith("#")]
        if not linhas:
            continue
        reg = {k.strip(): env.from_string(v.strip()).render(**ctx).strip() for k, _, v in (l.partition(":") for l in linhas)}
        fontes = [d.strip() for d in reg["D"].split(";") if d.strip()]
        for d in fontes:
            if not (RAIZ / d).exists():
                erros.append(f"fonte inexistente: {d}")
        if normaliza(reg["Q"]) in proibidas:
            erros.append(f"pergunta repetida do treino/teste/avaliação: {reg['Q']}")
        if reg["B"] == "responder":
            base = "\n".join(ler_doc(d)[1] if d.endswith(".md") else (RAIZ / d).read_text(encoding="utf-8") for d in fontes)
            digitos = re.sub(r"[.,]", "", base)
            for n in NUM_RE.findall(reg["A"]):
                if n not in base and re.sub(r"[.,]", "", n) not in digitos:
                    erros.append(f"número {n!r} ausente na fonte: {reg['Q'][:60]}")
        itens.append({"pergunta": reg["Q"], "resposta_esperada": reg["A"], "fonte_doc": fontes, "tipo": reg["T"],
                      "perfil": reg["P"], "comportamento": reg["B"]})
    assert not erros, "\n".join(erros)
    assert len(itens) == 20, f"esperado 20 itens de acesso, há {len(itens)}"
    escrever_jsonl("avaliacao/perguntas_acesso.jsonl", itens)
    print("acesso:", len(itens), dict(Counter(i["comportamento"] for i in itens)), dict(Counter(i["perfil"] for i in itens)))


if __name__ == "__main__":
    main()
