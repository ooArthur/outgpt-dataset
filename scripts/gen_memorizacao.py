"""Gera qa/qa_memorizacao_treino.jsonl e qa/qa_memorizacao_teste.jsonl: perguntas DIRETAS (sem contexto) sobre fatos `rag`.

Servem ao cenário "ajustado sem RAG" (E/F do README): medem quanto o modelo memoriza sozinho. Ficam fora de qa_treino/qa_teste
de propósito, pois o validador proíbe pergunta direta de fato rag nesses arquivos. Só entram fatos do split de TREINO de
qa_treino.jsonl (os fatos do teste continuam inéditos) e fora de documentos revogados (alvos contraditórios).
"""
import random
import re

from common import RAIZ, SYSTEM_PROMPT, carregar_ficha, escrever_jsonl, ler_doc, ler_jsonl, normaliza
from gen_qa import formal, informal, typo


def perguntas_avaliacao_txt():
    """Linhas Q: de templates/avaliacao.txt (sem Jinja), para evitar dependência circular com gen_avaliacao."""
    qs = set()
    for l in (RAIZ / "templates" / "avaliacao.txt").read_text(encoding="utf-8").splitlines():
        if l.startswith("Q:"):
            qs.add(normaliza(re.sub(r"\{\{.*?\}\}", "", l[2:])))
    return qs


def perguntas_qa():
    qs = set()
    for arq in ("qa/qa_treino.jsonl", "qa/qa_teste.jsonl"):
        for r in ler_jsonl(arq):
            for m in r["messages"]:
                if m["role"] == "user":
                    qs.add(normaliza(m["content"].split("PERGUNTA:")[-1]))
    return qs


def par(fato, pergunta, estilo):
    return {"messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": pergunta},
                         {"role": "assistant", "content": fato["resposta"]}],
            "meta": {"fato_id": fato["fato_id"], "tipo": "direta_memorizacao", "area": fato["area"], "fonte_doc": fato["fonte_doc"],
                     "estilo": estilo, "sensibilidade": fato["sensibilidade"], "destino": "rag"}}


def revogado(rel):
    return rel.endswith(".md") and ler_doc(rel)[0].get("status") == "revogada"


def main():
    ficha = carregar_ficha()
    rng = random.Random(ficha["empresa"]["seed"] + 11)
    fatos = ler_jsonl("fatos/fatos.jsonl")
    ids_treino = {r["meta"]["fato_id"] for r in ler_jsonl("qa/qa_treino.jsonl") if r["meta"]["tipo"] in ("direta", "com_contexto")}
    elegiveis = sorted((f for f in fatos if f["destino"] == "rag" and f["fato_id"] in ids_treino and not revogado(f["fonte_doc"])),
                       key=lambda f: f["fato_id"])
    proibidas = perguntas_qa() | perguntas_avaliacao_txt()
    treino, teste, vistas_treino, puladas = [], [], set(), 0
    for f in elegiveis:
        p0, p1 = f["perguntas"][:2]
        for est, q in (("formal", p0), ("formal", p1), ("informal", informal(p0, rng)), ("formal", formal(p1, rng))):
            if normaliza(q) not in vistas_treino:
                vistas_treino.add(normaliza(q))
                treino.append(par(f, q, est))
    for f in elegiveis:
        base = informal(f["perguntas"][1], rng)
        for est, q in (("informal", base), ("erro_digitacao", typo(base, rng))):
            n = normaliza(q)
            if n not in vistas_treino and n not in proibidas:
                vistas_treino.add(n)
                teste.append(par(f, q, est))
                break
        else:
            puladas += 1
    escrever_jsonl("qa/qa_memorizacao_treino.jsonl", treino)
    escrever_jsonl("qa/qa_memorizacao_teste.jsonl", teste)
    print(f"memorização: {len(elegiveis)} fatos rag elegíveis -> treino={len(treino)} teste={len(teste)} (fatos sem formulação inédita: {puladas})")


if __name__ == "__main__":
    main()
