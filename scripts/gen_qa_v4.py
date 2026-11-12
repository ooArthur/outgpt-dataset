"""Gera exemplos extras do v4 e o conjunto export/sft_treino_v4.jsonl (= v3 + extras do v4).

Motivo: no v3 a recusa piorou quando há RAG (fora de escopo 75% -> 62%; alucinação em "sem resposta" 0% -> 20%), porque todos os
exemplos novos tinham a resposta no contexto. Aqui o CONTEXTO vem do MESMO recuperador BM25 usado na avaliação (rag/buscar.py),
inclusive quando os trechos são irrelevantes, e o modelo aprende a recusar nesses casos.

Tipos:
  recusa_fora_rag   pergunta fora do escopo + trechos que o BM25 devolve (às vezes nenhum)
  recusa_sem_rag    pergunta sem resposta nos documentos + trechos recuperados (relacionados, mas insuficientes)
  resposta_rag      pergunta respondível, com os trechos reais do BM25 (o trecho certo precisa estar entre eles), para não virar recusa em tudo

Uso: python scripts/gen_qa_v4.py   (exige export/sft_treino_v3.jsonl, gerado por scripts/gen_qa_v3.py)
"""
import random
import sys
from collections import Counter

from common import RAIZ, AREAS_SUG, RESP_FORA, SEM_RESP_VARIANTES, carregar_ficha, escrever_jsonl, ler_jsonl, normaliza
from gen_qa import PESOS_RECUSA, FORA, informal, msgs, sem_resposta
import gen_qa_v3 as v3

sys.path.insert(0, str(RAIZ / "rag"))
from buscar import buscar, montar_prompt  # noqa: E402

PERFIS = ["colaborador", "colaborador", "gestor", "rh", "financeiro", "diretoria", "diretoria"]
FORA_NOVAS = [
    "Qual a melhor forma de aprender inglês rapidamente?", "Me explica o que é blockchain.", "Como faço um bolo de chocolate fofinho?",
    "Qual a população do Japão?", "Me indica um livro de ficção científica.", "Quem pintou a Mona Lisa?", "Qual o melhor smartphone para jogos?",
    "Como funciona a fotossíntese?", "Me ajuda a planejar uma festa de aniversário infantil?", "Qual a diferença entre vírus e bactéria?",
    "Escreva um poema sobre a chuva.", "Como faço para economizar na conta de luz da minha casa?", "Quais são os melhores exercícios para fortalecer as costas?",
    "Me explica o que é inflação.", "Qual o maior rio do mundo?", "Como montar um computador gamer?", "Me conta uma curiosidade sobre o espaço.",
    "Quem foi Santos Dumont?", "Escreva uma mensagem de feliz natal para a minha família.", "Qual a receita de um bom café coado?",
    "Como faço para tirar o passaporte?", "Qual o melhor momento para comprar dólar?", "Me explica como funciona um motor a combustão.",
    "Qual é a capital do Canadá?", "Resolva: quanto é 345 vezes 12?", "Escreva um código em JavaScript que inverta uma string.",
    "Como treinar um cachorro para não latir?", "Me recomenda uma série para maratonar.", "O que significa a palavra efêmero?",
    "Como faço para cuidar de uma planta suculenta?", "Qual a melhor época para viajar para Gramado?", "Quais são os planetas do sistema solar?",
    "Como faço um bom molho de tomate caseiro?", "Explique o que é machine learning para uma criança.", "Qual o melhor plano de celular para uso pessoal?",
    "Me fala sobre a Segunda Guerra Mundial.", "Como funciona o sistema de votação das eleições?", "Me ajuda a escolher uma faculdade?",
    "Quanto custa um apartamento em Campinas?", "Como faço para perder barriga?",
]


def main():
    ficha = carregar_ficha()
    rng = random.Random(ficha["empresa"]["seed"] + 41)
    S = v3.Saida()
    itens = []

    def add(tipo, pergunta, resposta, perfil, checar_eval=True, **meta):
        chave = normaliza(pergunta) + "|" + perfil
        if chave in S.usadas:
            return False
        if checar_eval and v3.perto_da_avaliacao(pergunta):
            S.rej["parecida_com_avaliacao"] += 1
            return False
        S.usadas.add(chave)
        trechos = buscar(pergunta, k=4, perfil=perfil)
        user = montar_prompt(pergunta, trechos) if trechos else pergunta
        itens.append({"messages": msgs(user, resposta), "meta": {"tipo": tipo, "perfil": perfil, "n_trechos": len(trechos), **meta}})
        return True

    # recusa: fora de escopo
    foras = list(dict.fromkeys(FORA + FORA_NOVAS))
    n = 0
    for q in foras:
        for v in (q, informal(q, rng)):
            for _ in range(2):  # dois perfis diferentes por pergunta
                n += add("recusa_fora_rag", v, RESP_FORA[n % len(RESP_FORA)], rng.choice(PERFIS))

    # recusa: sem resposta nos documentos
    sr = sem_resposta(v3.ctxs, ficha, rng)
    rng.shuffle(sr)
    feitos = 0
    for it in sr:
        if feitos >= 360:
            break
        variante = rng.choices(SEM_RESP_VARIANTES, weights=PESOS_RECUSA)[0]
        if add("recusa_sem_rag", it["q"], variante.format(area=AREAS_SUG[it["area"]]), rng.choice(PERFIS), area=it["area"]):
            feitos += 1

    # respostas com os trechos reais do BM25 (o trecho certo tem que estar entre eles)
    treino_ids = {r["meta"]["fato_id"] for r in ler_jsonl("qa/qa_treino.jsonl") if r["meta"]["tipo"] in ("direta", "com_contexto", "multi_turno")}
    fatos = [f for f in ler_jsonl("fatos/fatos.jsonl") if f["fato_id"] in treino_ids and f["fonte_doc"].endswith(".md") and f["sensibilidade"] == "publico"]
    rng.shuffle(fatos)
    pos = 0
    for f in fatos:
        if pos >= 320:
            break
        q = rng.choice(f["perguntas"])
        q = informal(q, rng) if rng.random() < 0.3 else q
        perfil = rng.choice(PERFIS)
        trechos = buscar(q, k=4, perfil=perfil)
        if not any(f["evidencia"] and f["evidencia"] in t["texto"] for t in trechos):
            S.rej["evidencia_fora_do_top4"] += 1
            continue
        if add("resposta_rag", q, f["resposta"], perfil, fato_id=f["fato_id"]):
            pos += 1

    rng.shuffle(itens)
    escrever_jsonl("qa/qa_v4_extra.jsonl", itens)
    base = ler_jsonl("export/sft_treino_v3.jsonl")
    todos = base + [{"messages": r["messages"]} for r in itens]
    random.Random(ficha["empresa"]["seed"] + 54).shuffle(todos)
    escrever_jsonl("export/sft_treino_v4.jsonl", todos)
    print("extras v4:", len(itens), dict(Counter(r["meta"]["tipo"] for r in itens)))
    print("com 0 trechos recuperados:", sum(1 for r in itens if r["meta"]["n_trechos"] == 0), "| descartes:", dict(S.rej))
    print("export/sft_treino_v4.jsonl:", len(todos), "exemplos")


if __name__ == "__main__":
    main()
