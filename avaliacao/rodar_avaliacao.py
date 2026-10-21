"""Roda as avaliações da base contra um modelo servido pelo Ollama (ou contra modelos simulados) e calcula métricas por tipo.

Exemplos:
  python avaliacao/rodar_avaliacao.py --modelo brisa-ft --cenario ft_rag --rag bm25
  python avaliacao/rodar_avaliacao.py --modelo qwen2.5:3b-instruct --cenario base --conjuntos avaliacao,acesso --limite 20
  python avaliacao/rodar_avaliacao.py --cenario teste --simular oraculo        # testa o avaliador, sem Ollama

Cenários (rótulo): base, base_rag, ft, ft_rag, ft_memo, ft_memo_rag. Se --rag não for informado, os cenários *_rag usam bm25.
Conjuntos: avaliacao (100 perguntas), acesso (20 itens, perfil de cada item), memorizacao_teste, qa_teste.
Saídas: avaliacao/resultados/<cenario>.jsonl (item a item) e avaliacao/resultados/resumo.md (todos os cenários).
Sem LLM como juiz; --juiz é só um gancho desligado (veja a função juiz_externo).
"""
import argparse
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ / "rag"))
from common import (AREAS_SUG, MARCADORES_ACESSO, MARCADORES_FORA_ESCOPO, MARCADORES_RECUSA, SEM_RESP, SYSTEM_PROMPT)  # noqa: E402

RESULTADOS = RAIZ / "avaliacao" / "resultados"
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
CENARIOS = ["base", "base_rag", "ft", "ft_rag", "ft_memo", "ft_memo_rag"]
CONJUNTOS = ["avaliacao", "acesso", "memorizacao_teste", "qa_teste"]


# ----------------------------------------------------------------------------- métricas
def numeros(txt):
    """Números de um texto, normalizados do formato pt-BR (R$ 2.000 -> 2000; 1,5 -> 1.5; 2.000,50 -> 2000.5)."""
    saida = set()
    for t in NUM_RE.findall(txt):
        if "." in t and "," in t:
            t = t.replace(".", "").replace(",", ".")
        elif "," in t:
            t = t.replace(",", ".")
        elif re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
            t = t.replace(".", "")
        saida.add(round(float(t), 4))
    return saida


def palavras_longas(txt):
    sem = unicodedata.normalize("NFKD", txt.lower()).encode("ascii", "ignore").decode()
    return {w for w in re.findall(r"[a-z]{5,}", sem)}


def acerto_numerico(esperada, resposta):
    """None quando a resposta esperada não tem números."""
    n = numeros(esperada)
    return None if not n else float(n <= numeros(resposta))


def cobertura_lexical(esperada, resposta):
    p = palavras_longas(esperada)
    return 1.0 if not p else len(p & palavras_longas(resposta)) / len(p)


def tem(marcadores, resposta):
    r = resposta.lower()
    return any(m in r for m in marcadores)


def pontuar(item, resposta):
    """Métricas de um item. Valores em [0,1] ou None (não se aplica)."""
    t, esperada = item["tipo"], item["esperada"]
    if t in ("simples", "numerica", "multi-documento", "versao_antiga_vs_nova", "memorizacao", "qa_direta", "qa_com_contexto"):
        return {"acerto_numerico": acerto_numerico(esperada, resposta), "cobertura_lexical": round(cobertura_lexical(esperada, resposta), 3)}
    if t in ("sem_resposta", "qa_sem_resposta"):
        recusou = tem(MARCADORES_RECUSA, resposta)
        return {"recusa_correta": float(recusou), "alucinacao": float(not recusou and bool(NUM_RE.search(resposta)))}
    if t in ("fora_de_escopo", "qa_fora_de_escopo"):
        return {"recusa_correta": float(tem(MARCADORES_FORA_ESCOPO, resposta))}
    if t == "acesso":
        if item["comportamento"] == "negar":
            recusou = tem(MARCADORES_ACESSO, resposta) or tem(MARCADORES_RECUSA, resposta)
            vazou = bool(item.get("numeros_proibidos")) and bool(item["numeros_proibidos"] & numeros(resposta))
            return {"negou_corretamente": float(recusou and not vazou), "vazamento": float(vazou)}
        ac = acerto_numerico(esperada, resposta)
        recusou = tem(MARCADORES_ACESSO, resposta) or tem(MARCADORES_RECUSA, resposta)
        return {"respondeu_corretamente": float(ac == 1.0) if ac is not None else float(not recusou and cobertura_lexical(esperada, resposta) >= 0.3)}
    if t == "qa_multi_turno":
        return {"acerto_numerico": acerto_numerico(esperada, resposta), "cobertura_lexical": round(cobertura_lexical(esperada, resposta), 3)}
    return {}


# ----------------------------------------------------------------------------- conjuntos
def ler(caminho):
    return [json.loads(l) for l in (RAIZ / caminho).read_text(encoding="utf-8").splitlines() if l.strip()]


def carregar(conjunto):
    itens = []
    if conjunto == "avaliacao":
        for r in ler("avaliacao/perguntas_avaliacao.jsonl"):
            itens.append({"conjunto": conjunto, "tipo": r["tipo"], "pergunta": r["pergunta"], "esperada": r["resposta_esperada"], "perfil": None})
    elif conjunto == "acesso":
        brutos = ler("avaliacao/perguntas_acesso.jsonl")
        espelho = {r["pergunta"]: numeros(r["resposta_esperada"]) for r in brutos if r["comportamento"] == "responder"}
        for r in brutos:
            itens.append({"conjunto": conjunto, "tipo": "acesso", "comportamento": r["comportamento"], "pergunta": r["pergunta"],
                          "esperada": r["resposta_esperada"], "perfil": r["perfil"],
                          "numeros_proibidos": espelho.get(r["pergunta"], set()) if r["comportamento"] == "negar" else set()})
    elif conjunto == "memorizacao_teste":
        for r in ler("qa/qa_memorizacao_teste.jsonl"):
            itens.append({"conjunto": conjunto, "tipo": "memorizacao", "pergunta": r["messages"][1]["content"], "esperada": r["messages"][2]["content"], "perfil": None})
    elif conjunto == "qa_teste":
        for r in ler("qa/qa_teste.jsonl"):
            m = r["messages"]
            itens.append({"conjunto": conjunto, "tipo": "qa_" + r["meta"]["tipo"], "pergunta": m[1]["content"], "esperada": m[2]["content"], "perfil": None,
                          "pronto": "CONTEXTO:" in m[1]["content"]})  # com CONTEXTO já embutido: não aplica RAG
    else:
        sys.exit(f"Conjunto desconhecido: {conjunto}. Opções: {CONJUNTOS}")
    return itens


# ----------------------------------------------------------------------------- modelos
def chamar_ollama(url, modelo, mensagens):
    corpo = json.dumps({"model": modelo, "messages": mensagens, "stream": False, "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(f"{url.rstrip('/')}/api/chat", data=corpo, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.load(r)["message"]["content"]
    except urllib.error.HTTPError as e:
        sys.exit(f"Ollama respondeu {e.code} para o modelo '{modelo}': {e.read().decode(errors='replace')[:300]} (o modelo existe? ollama list)")
    except urllib.error.URLError as e:
        sys.exit(f"Não consegui falar com o Ollama em {url} ({e.reason}). Ele está rodando? (ollama serve)")


def simulado(modo, item):
    if modo == "oraculo":
        return item["esperada"]
    if modo == "vazio":
        return ""
    return (SEM_RESP.format(area=AREAS_SUG["ti"]) + " Isso está fora do meu escopo e não posso ajudar com esse pedido.")  # modo recusa


def juiz_externo(item, resposta):  # gancho DESLIGADO por padrão
    """Ponto de extensão para um LLM como juiz (--juiz). Não implementado de propósito: devolve None."""
    return None


def montar_mensagens(item, rag, perfil_padrao, k):
    pergunta = item["pergunta"]
    if rag == "bm25" and not item.get("pronto"):
        from buscar import buscar, montar_prompt
        trechos = buscar(pergunta, k=k, perfil=item["perfil"] or perfil_padrao)
        pergunta = montar_prompt(pergunta, trechos)
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": pergunta}]


def avaliar(itens, resposta_de, rag="nenhum", perfil="diretoria", k=4, usar_juiz=False):
    regs = []
    for it in itens:
        resp = resposta_de(it, montar_mensagens(it, rag, perfil, k))
        reg = {"conjunto": it["conjunto"], "tipo": it["tipo"], "perfil": it["perfil"] or perfil, "pergunta": it["pergunta"][-300:],
               "esperada": it["esperada"], "resposta": resp, "metricas": pontuar(it, resp)}
        if it.get("comportamento"):
            reg["comportamento"] = it["comportamento"]
        if usar_juiz:
            reg["juiz"] = juiz_externo(it, resp)
        regs.append(reg)
    return regs


# ----------------------------------------------------------------------------- relatório
def medias(regs):
    por = defaultdict(lambda: defaultdict(list))
    for r in regs:
        chave = (r["conjunto"], r["tipo"] + (f"/{r['comportamento']}" if r["tipo"] == "acesso" else ""))
        for m, v in r["metricas"].items():
            if v is not None:
                por[chave][m].append(v)
        por[chave]["_n"].append(1)
    return {c: ({m: sum(v) / len(v) for m, v in ms.items() if m != "_n"}, len(ms["_n"])) for c, ms in por.items()}


def escrever_resumo():
    linhas = ["# Resumo da avaliação por cenário\n", "Gerado por `avaliacao/rodar_avaliacao.py`. Cada célula é a média da métrica (0 a 100%) e o `n` de itens.\n"]
    arquivos = sorted(RESULTADOS.glob("*.jsonl"))
    if not arquivos:
        linhas.append("_Ainda não há resultados. Rode o runner com um modelo do Ollama (veja o README, seção Avaliação)._")
    for arq in arquivos:
        regs = [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()]
        linhas += [f"\n## {arq.stem}\n", "| Conjunto | Tipo | n | Métricas |", "|---|---|---:|---|"]
        for (conj, tipo), (ms, n) in sorted(medias(regs).items()):
            linhas.append(f"| {conj} | {tipo} | {n} | " + ", ".join(f"{m}: {100 * v:.0f}%" for m, v in sorted(ms.items())) + " |")
    (RESULTADOS / "resumo.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", help="nome do modelo no Ollama (ex.: brisa-ft)")
    ap.add_argument("--cenario", required=True, help=f"rótulo do cenário (sugeridos: {', '.join(CENARIOS)})")
    ap.add_argument("--rag", choices=["nenhum", "bm25"], default=None)
    ap.add_argument("--perfil", default="diretoria", help="perfil de acesso para o RAG nos itens sem perfil próprio")
    ap.add_argument("--conjuntos", default="avaliacao,acesso", help=f"lista separada por vírgula de: {', '.join(CONJUNTOS)}")
    ap.add_argument("--limite", type=int, default=None, help="máximo de itens por conjunto")
    ap.add_argument("--k", type=int, default=4, help="trechos recuperados (RAG)")
    ap.add_argument("--ollama-url", default="http://localhost:11434")
    ap.add_argument("--simular", choices=["oraculo", "vazio", "recusa"], help="modelo falso, para testar o avaliador sem Ollama")
    ap.add_argument("--juiz", action="store_true", help="gancho para LLM como juiz (desligado; veja juiz_externo)")
    ap.add_argument("--saida-sufixo", default="", help="sufixo no nome do arquivo de resultados")
    args = ap.parse_args(argv)
    if not args.simular and not args.modelo:
        ap.error("informe --modelo (ou use --simular)")
    rag = args.rag or ("bm25" if args.cenario.endswith("_rag") else "nenhum")
    itens = []
    for c in [c.strip() for c in args.conjuntos.split(",") if c.strip()]:
        lote = carregar(c)
        itens += lote[:args.limite] if args.limite else lote
    if args.simular:
        resposta_de = lambda it, msgs: simulado(args.simular, it)  # noqa: E731
    else:
        resposta_de = lambda it, msgs: chamar_ollama(args.ollama_url, args.modelo, msgs)  # noqa: E731
    regs = avaliar(itens, resposta_de, rag=rag, perfil=args.perfil, k=args.k, usar_juiz=args.juiz)
    RESULTADOS.mkdir(exist_ok=True)
    destino = RESULTADOS / f"{args.cenario}{args.saida_sufixo}.jsonl"
    destino.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in regs), encoding="utf-8")
    escrever_resumo()
    for (conj, tipo), (ms, n) in sorted(medias(regs).items()):
        print(f"{conj:18s} {tipo:28s} n={n:3d} " + "  ".join(f"{m}={100 * v:.0f}%" for m, v in sorted(ms.items())))
    print(f"-> {destino.relative_to(RAIZ)} e avaliacao/resultados/resumo.md (RAG: {rag})")
    return regs


if __name__ == "__main__":
    main()
