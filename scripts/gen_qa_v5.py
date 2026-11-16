"""Gera exemplos extras do v5 e o conjunto export/sft_treino_v5.jsonl (= v4 + extras do v5).

Motivo (erros do v3 com RAG): (a) o treino não tinha NENHUM exemplo da mensagem de acesso restrito, então o modelo não sabia negar
quando o filtro de acesso tira o documento do contexto; (b) contas erradas (120 km x R$ 1,20 = "R$ 14,40"); (c) poucas contas de margem
e de orçado x realizado.

Tipos (o CONTEXTO vem do mesmo BM25 da avaliação, já filtrado pelo perfil, exceto nas contas):
  acesso_negar      fato restrito + perfil sem acesso (o trecho não aparece no contexto) -> mensagem de acesso restrito
  acesso_responder  o mesmo tipo de pergunta com um perfil que tem acesso e o trecho certo no top-4 -> resposta
  conta_explicita   contas com a operação escrita ("120 x R$ 1,20 = R$ 144,00"), margens trimestrais e saldo do orçamento

Uso: python scripts/gen_qa_v5.py   (exige export/sft_treino_v4.jsonl, gerado por scripts/gen_qa_v4.py)
"""
import random
import re
import sys
from collections import Counter

from acesso import mensagem_negado, pode_ver
from common import RAIZ, AREAS_SUG, brl, brl2, carregar_ficha, escrever_jsonl, ler_jsonl, normaliza, pct
from gen_qa import informal, formal, msgs
import gen_qa_v3 as v3

sys.path.insert(0, str(RAIZ / "rag"))
from buscar import buscar, montar_prompt  # noqa: E402

PERFIS = ["colaborador", "gestor", "rh", "financeiro", "diretoria"]


def main():
    ficha = carregar_ficha()
    rng = random.Random(ficha["empresa"]["seed"] + 61)
    S = v3.Saida()
    itens = []

    def add_rag(tipo, pergunta, resposta, perfil, **meta):
        chave = normaliza(pergunta) + "|" + perfil
        if chave in S.usadas:
            return False
        if v3.perto_da_avaliacao(pergunta):
            S.rej["parecida_com_avaliacao"] += 1
            return False
        S.usadas.add(chave)
        trechos = buscar(pergunta, k=4, perfil=perfil)
        user = montar_prompt(pergunta, trechos) if trechos else pergunta
        itens.append({"messages": msgs(user, resposta), "meta": {"tipo": tipo, "perfil": perfil, "n_trechos": len(trechos), **meta}})
        return True

    # ---------------------------------------------------------------- acesso
    treino_ids = {r["meta"]["fato_id"] for r in ler_jsonl("qa/qa_treino.jsonl") if r["meta"]["tipo"] in ("direta", "com_contexto", "multi_turno")}
    restritos = [f for f in ler_jsonl("fatos/fatos.jsonl") if f["fato_id"] in treino_ids and f["sensibilidade"] != "publico"]
    rng.shuffle(restritos)
    por_doc = Counter()
    for f in restritos:
        fonte = f["fonte_doc"]
        sem = [p for p in PERFIS if not pode_ver(p, fonte)]
        com = [p for p in PERFIS if pode_ver(p, fonte)]
        limite = 60 if "resumo-dre" in fonte else 999      # a DRE tem muitos fatos parecidos; não deixa dominar
        if por_doc[fonte] >= limite:
            continue
        por_doc[fonte] += 1
        qs = list(f["perguntas"][:2])
        variantes = [qs[0], informal(qs[1], rng), formal(qs[0], rng) if rng.random() < 0.5 else informal(qs[0], rng)]
        negado = mensagem_negado(AREAS_SUG[f["area"]])
        for q in variantes[:2]:
            add_rag("acesso_negar", q, negado, rng.choice(sem), fato_id=f["fato_id"])
        q = variantes[2] if rng.random() < 0.5 else qs[1]
        perfil = rng.choice(com)
        trechos = buscar(q, k=4, perfil=perfil)
        if f["evidencia"] and any(f["evidencia"] in t["texto"] for t in trechos):
            add_rag("acesso_responder", q, f["resposta"], perfil, fato_id=f["fato_id"])
        else:
            S.rej["evidencia_fora_do_top4"] += 1

    # ---------------------------------------------------------------- contas com a operação escrita
    def conta(pergunta, trechos, resposta, sub):
        try:
            S.add("conta_explicita", pergunta, trechos, resposta, rng, checar=False, sub=sub)
        except AssertionError:
            pass
        if S.itens:
            itens.append(S.itens.pop())

    for n in v3.livre(rng, (15, 780), 5, 45):
        if n == 120:
            continue
        q = rng.choice([f"Fiz {n} km com meu carro a serviço, com aprovação prévia. Qual o valor do reembolso?",
                        f"Quanto dá o reembolso de quilometragem de {n} km?", f"Usei meu carro por {n} km em visita a cliente, com aprovação. Quanto recebo?"])
        conta(v3.variante(q, rng), [v3.ch(v3.RE_NEW, "## O que é reembolsável")],
              f"A quilometragem com carro próprio, com aprovação prévia, é reembolsada a R$ 1,20 por km. Conta: {n} × R$ 1,20 = {brl2(n * 1.2)}.", "km")
    for d in [x for x in range(8, 24) if x != 22]:
        q = rng.choice([f"Num mês com {d} dias trabalhados, quanto recebo de VR?", f"Quanto de vale-refeição cai em um mês em que trabalhei {d} dias?"])
        conta(v3.variante(q, rng), [v3.ch_com(v3.BEN, "Vale-refeição")], f"O VR é de R$ 42 por dia trabalhado. Conta: {d} × R$ 42 = {brl(d * 42)}.", "vr")
    servicos = []
    for linha in (RAIZ / v3.PORT).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| ([A-Z]{3}-\d{3}) \| (.+?) \| (.+?) \| R\$ ([\d.,]+) \|", linha)
        if m and m.group(3) in v3.UN:
            servicos.append((m.group(1), m.group(2), m.group(3), v3.num_br(m.group(4))))
    for cod, nome, cob, preco in servicos:
        sing, plur = v3.UN[cob]
        for n in v3.livre(rng, (4, 700), 1, 7):
            if n in (200, 50):
                continue
            q = rng.choice([f"Pela tabela, quanto fica {n} {plur} de {nome.lower()}?", f"Preciso de um orçamento de tabela: {n} {plur}, serviço {nome.lower()}."])
            por = sing + (" ao mês" if "/mês" in cob else "")
            conta(v3.variante(q, rng), [v3.ch_com(v3.PORT, cod)],
                  f"{nome} ({cod}) custa {brl2(preco)} por {por}. Conta: {n} × {brl2(preco)} = {brl2(n * preco)}, antes de eventuais descontos.", "tabela_preco")

    tri = v3.tabela_trimestral()
    for t, v in tri.items():
        for nome, k, rot in (("lb", "margem bruta", "lucro bruto"), ("ebitda", "margem EBITDA", "EBITDA")):
            q = rng.choice([f"Qual foi a {k} do trimestre {t}?", f"Em {t}, quanto o {rot} representou da receita líquida?"])
            conta(q, [v3.ch_com(v3.DRE, "| 2024T1")],
                  f"Em {t}, o {rot} foi de {brl(v[nome])} e a receita líquida, de {brl(v['rl'])}. Conta: {brl(v[nome])} ÷ {brl(v['rl'])} = {pct(v[nome] / v['rl'] * 100, 1)}.",
                  "margem_trimestral")
    for linha in (RAIZ / v3.ORC).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| (.+?) \| R\$ ([\d.]+) \| R\$ ([\d.]+) \| (-?)R\$ ([\d.]+) \|", linha)
        if not m or m.group(1) == "Operações e Logística":
            continue
        dep, orc, real, sinal, saldo = m.group(1), v3.num_br(m.group(2)), v3.num_br(m.group(3)), m.group(4), v3.num_br(m.group(5))
        situ = "gastou acima do orçado" if sinal else "gastou abaixo do orçado"
        for q in (f"No 1º semestre de 2026, {dep} gastou mais ou menos do que o orçado?", f"Qual o saldo do orçamento de {dep} no primeiro semestre de 2026?"):
            conta(q, [v3.ch_com(v3.ORC, "Orçado 1º semestre")],
                  f"No 1º semestre de 2026, {dep} tinha {brl(orc)} orçados e realizou {brl(real)}. Conta: {brl(orc)} − {brl(real)} = {sinal}{brl(saldo)}, ou seja, {situ}.",
                  "orcado_realizado")

    rng.shuffle(itens)
    escrever_jsonl("qa/qa_v5_extra.jsonl", itens)
    base = ler_jsonl("export/sft_treino_v4.jsonl")
    todos = base + [{"messages": r["messages"]} for r in itens]
    random.Random(ficha["empresa"]["seed"] + 55).shuffle(todos)
    escrever_jsonl("export/sft_treino_v5.jsonl", todos)
    print("extras v5:", len(itens), dict(Counter(r["meta"]["tipo"] for r in itens)))
    print("subtipos:", dict(Counter(r["meta"].get("sub") for r in itens if r["meta"].get("sub"))), "| fatos restritos por doc:", dict(por_doc))
    print("descartes:", dict(S.rej))
    print("export/sft_treino_v5.jsonl:", len(todos), "exemplos | maior (chars):", max(len(str(r["messages"])) for r in todos))


if __name__ == "__main__":
    main()
