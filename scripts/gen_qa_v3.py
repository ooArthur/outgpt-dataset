"""Gera exemplos extras de treino (v3) e o conjunto export/sft_treino_v3.jsonl.

Motivo: no v2 o modelo errava perguntas que exigem (a) escolher a faixa certa de uma tabela, (b) fazer contas com o contexto,
(c) separar a regra de 2025 (revogada) da de 2026 e (d) juntar dois documentos. O conjunto base só tinha um fato por pergunta.

Tipos gerados (todos com CONTEXTO no formato do RAG, trechos reais dos documentos, e sem tocar na divisão treino/teste):
  faixa_valor  alçadas, compras, brindes, reembolso: aplicar a faixa/limite ao valor da pergunta
  aritmetica   preço de tabela x quantidade, VR x dias, PLR, somas/diferenças/margens do DRE, diferença de orçamentos
  versao       regra de 2025 (revogada) x 2026, inclusive com valor numérico
  multi_doc    duas perguntas de documentos diferentes numa só (só fatos públicos da divisão de treino)

Garantias: valores e perguntas que aparecem na avaliação são excluídos; perguntas parecidas com as da avaliação
(Jaccard >= 0,6) são descartadas; nos tipos sem conta, todo número da resposta tem que estar no contexto.

Uso: python scripts/gen_qa_v3.py   (gera qa/qa_v3_extra.jsonl e export/sft_treino_v3.jsonl)
"""
import random
import re
from collections import Counter

from common import RAIZ, brl, brl2, carregar_ficha, escrever_jsonl, ler_jsonl, normaliza, pct
from gen_qa import Contextos, informal, lower_first, montar_contexto, msgs

NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
DOCS = ["institucional", "rh", "financeiro", "ti", "comercial", "compliance"]

AL_NEW, AL_OLD = "docs/financeiro/alcadas-aprovacao.md", "docs/financeiro/alcadas-aprovacao-v2025.md"
CP = "docs/financeiro/politica-compras.md"
BR_NEW, BR_OLD = "docs/compliance/politica-brindes.md", "docs/compliance/politica-brindes-v2025.md"
RE_NEW, RE_OLD = "docs/financeiro/reembolso.md", "docs/financeiro/reembolso-v2025.md"
HO_NEW, HO_OLD = "docs/rh/home-office.md", "docs/rh/home-office-v2025.md"
PORT, BEN, PLR = "docs/comercial/portfolio-servicos.md", "docs/rh/beneficios.md", "docs/rh/plr.md"
DRE, ORC = "docs/financeiro/resumo-dre.md", "docs/financeiro/orcamento-departamentos.md"

ctxs = Contextos()
Contextos.todos_docs = sorted(f"docs/{a}/{p.stem}.md" for a in DOCS for p in (RAIZ / "docs" / a).glob("*.md"))


def ch(rel, inicio):
    for c in ctxs.chunks(rel)[1]:
        if c.startswith(inicio):
            return rel, c
    raise AssertionError((rel, inicio))


def ch_com(rel, trecho):
    for c in ctxs.chunks(rel)[1]:
        if trecho in c:
            return rel, c
    raise AssertionError((rel, trecho))


def contexto(trechos, q, rng, distrator=0.5):
    t = list(trechos)
    if rng.random() < distrator:
        usados = {r for r, _ in t}
        d = rng.choice([p for p in Contextos.todos_docs if p not in usados])
        t.append((d, rng.choice(ctxs.chunks(d)[1])))
    rng.shuffle(t)
    return montar_contexto(t, q)


def toks(q):
    return set(normaliza(q).split())


def num_br(s):
    return float(s.replace(".", "").replace(",", "."))


# ------------------------------------------------------------------ avaliação (para excluir)
AVAL = [r["pergunta"] for r in ler_jsonl("avaliacao/perguntas_avaliacao.jsonl")] + \
       [r["pergunta"] for r in ler_jsonl("avaliacao/perguntas_acesso.jsonl")]
AVAL_TOK = [toks(q) for q in AVAL]
AVAL_NUM = {n.replace(".", "") for q in AVAL for n in NUM_RE.findall(q)}


def perto_da_avaliacao(q):
    t = toks(q)
    return any(len(t & a) / max(1, len(t | a)) >= 0.6 for a in AVAL_TOK)


class Saida:
    def __init__(self):
        self.itens, self.usadas, self.rej = [], set(), Counter()
        for arq in ("qa/qa_treino.jsonl", "qa/qa_teste.jsonl", "qa/qa_memorizacao_treino.jsonl", "qa/qa_memorizacao_teste.jsonl"):
            for r in ler_jsonl(arq):
                for m in r["messages"]:
                    if m["role"] == "user":
                        self.usadas.add(normaliza(m["content"].split("PERGUNTA:")[-1]))

    def add(self, tipo, pergunta, trechos, resposta, rng, checar=True, distrator=0.5, **meta):
        chave = normaliza(pergunta)
        if chave in self.usadas:
            self.rej["repetida"] += 1
            return False
        if perto_da_avaliacao(pergunta):
            self.rej["parecida_com_avaliacao"] += 1
            return False
        user = contexto(trechos, pergunta, rng, distrator)
        if checar:
            ctx_nums = {n for n in NUM_RE.findall(user)}
            falta = [n for n in NUM_RE.findall(resposta) if n not in ctx_nums and n not in ("2025", "2026")]
            if falta:
                self.rej["numero_fora_do_contexto"] += 1
                raise AssertionError(f"{tipo}: números {falta} fora do contexto: {pergunta!r} -> {resposta!r}")
        self.usadas.add(chave)
        self.itens.append({"messages": msgs(user, resposta), "meta": {"tipo": tipo, **meta}})
        return True


def variante(q, rng):
    return informal(q, rng) if rng.random() < 0.22 else q


def livre(rng, faixa, passo, n):
    """valores sem coincidir com números da avaliação"""
    out = []
    while len(out) < n:
        v = rng.randrange(faixa[0], faixa[1] + 1, passo)
        if str(v) not in AVAL_NUM:
            out.append(v)
    return out


# ------------------------------------------------------------------ faixas
OBJ = ["um servidor", "uma empilhadeira usada", "material de escritório", "etiquetas térmicas", "uma licença de software",
       "equipamentos de rede", "paletes de reposição", "um serviço de manutenção", "um lote de coletores de dados", "estantes porta-paletes"]
NOME_AP = {1: "gestor imediato", 2: "diretor da área", 3: "CEO"}


def faixa26(v):
    return 1 if v <= 2000 else 2 if v <= 20000 else 3


def faixa25(v):
    return 1 if v <= 1000 else 2 if v <= 10000 else 3


def resp_compra(v):
    f = faixa26(v)
    if f == 1:
        return f"Como o valor de {brl(v)} é de até R$ 2.000, a compra é direta, com uma cotação ou preço de tabela, e a aprovação é do gestor imediato."
    if f == 2:
        return f"Como o valor de {brl(v)} está acima de R$ 2.000 e até R$ 20.000, são necessárias no mínimo 3 cotações e a aprovação é do diretor da área."
    extra = " Por ser maior que R$ 200.000, a operação também é comunicada ao Conselho de Administração, para ciência." if v > 200000 else ""
    return f"Como o valor de {brl(v)} passa de R$ 20.000, é exigida concorrência formal com proposta escrita e a aprovação é do CEO." + extra


def gerar_faixas(S, rng):
    def valores(n):
        base = livre(rng, (200, 2000), 50, n // 3) + livre(rng, (2100, 20000), 100, n // 3) + livre(rng, (20500, 250000), 500, n - 2 * (n // 3))
        base += [2000, 2001, 20000, 20001]
        rng.shuffle(base)
        return [v for v in base if str(v) not in AVAL_NUM]

    for v in valores(130):
        o = rng.choice(OBJ)
        q = rng.choice([f"Preciso comprar {o} que custa {brl(v)}. Quem aprova e quantas cotações eu preciso?",
                        f"Vou contratar {o} por {brl(v)}. O que a política exige e quem aprova?",
                        f"Quero comprar {o} no valor de {brl(v)}. Como é o processo de cotação e aprovação?"])
        S.add("faixa_valor", variante(q, rng), [ch(AL_NEW, "## Tabela de alçadas"), ch(CP, "## Regra por faixa de valor")], resp_compra(v), rng, sub="compra")
    for v in valores(50):
        q = rng.choice([f"Quem aprova uma despesa de {brl(v)}?", f"Qual é a alçada para uma operação de {brl(v)}?",
                        f"Uma operação de {brl(v)} precisa de qual nível de aprovação?"])
        f = faixa26(v)
        r = f"Uma operação de {brl(v)} é aprovada pelo {NOME_AP[f]}."
        if v > 200000:
            r += " Como passa de R$ 200.000, ela também é levada ao Conselho de Administração, para ciência."
        S.add("faixa_valor", variante(q, rng), [ch(AL_NEW, "## Tabela de alçadas")], r, rng, sub="alcada")
    for v in valores(40):
        q = rng.choice([f"Quantas cotações preciso para uma compra de {brl(v)}?", f"Para comprar algo de {brl(v)}, preciso de quantas cotações?"])
        f = faixa26(v)
        r = {1: f"Para {brl(v)}, que é até R$ 2.000, a compra é direta, com uma cotação ou preço de tabela.",
             2: f"Para {brl(v)}, que fica acima de R$ 2.000 e até R$ 20.000, são necessárias no mínimo 3 cotações.",
             3: f"Para {brl(v)}, que passa de R$ 20.000, não bastam cotações: a política exige concorrência formal com proposta escrita."}[f]
        S.add("faixa_valor", variante(q, rng), [ch(CP, "## Regra por faixa de valor")], r, rng, sub="cotacoes")
    for v in livre(rng, (300, 30000), 100, 90):
        q = rng.choice([f"Em 2025, quem aprovava uma operação de {brl(v)}?", f"Pela tabela de 2025, quem aprovaria {brl(v)}?"])
        r = f"Pela tabela de 2025, já revogada, uma operação de {brl(v)} era aprovada pelo {NOME_AP[faixa25(v)]}."
        S.add("versao", q, [ch(AL_OLD, "## Tabela de 2025")], r, rng, sub="alcada25")
    for v in livre(rng, (1100, 19000), 100, 60):
        q = rng.choice([f"Uma compra de {brl(v)} seria aprovada por quem em 2025 e por quem é aprovada hoje?",
                        f"Quem aprovava {brl(v)} em 2025 e quem aprova agora?"])
        a, b = NOME_AP[faixa25(v)], NOME_AP[faixa26(v)]
        r = (f"Em 2025, a aprovação era do {a}. Hoje, na versão 2026, é do {b}." if a != b else
             f"Tanto em 2025 quanto hoje, na versão 2026, a aprovação é do {a}.")
        S.add("versao", q, [ch(AL_OLD, "## Tabela de 2025"), ch(AL_NEW, "## Tabela de alçadas")], r, rng, sub="alcada_comparacao")

    # brindes e hospitalidade
    for v in livre(rng, (40, 420), 5, 70):
        if rng.random() < 0.5:
            q = rng.choice([f"Um fornecedor quer me dar um presente de {brl(v)}. Posso aceitar?", f"Ganhei um brinde de {brl(v)} de um parceiro. Está dentro da política?"])
            r = (f"Sim. O limite para brinde ou presente é de até R$ 150 por pessoa e {brl(v)} está dentro dele." if v <= 150 else
                 f"Não. {brl(v)} ultrapassa o limite de R$ 150 por pessoa para brinde ou presente.")
        else:
            q = rng.choice([f"Um cliente me convidou para um jantar de {brl(v)} por pessoa. Está dentro da política?", f"Posso aceitar uma refeição de {brl(v)} por pessoa oferecida por um parceiro?"])
            r = (f"Sim. O limite para refeição ou hospitalidade é de até R$ 200 por pessoa e {brl(v)} está dentro dele." if v <= 200 else
                 f"Não. {brl(v)} ultrapassa o limite de R$ 200 por pessoa para refeição ou hospitalidade.")
        S.add("faixa_valor", variante(q, rng), [ch(BR_NEW, "## Limites\n")], r, rng, sub="brindes")
    for v in livre(rng, (90, 170), 5, 16):
        q = f"Recebi um presente de {brl(v)}. Estaria dentro do limite hoje? E em 2025?"
        h, o = v <= 150, v <= 100
        r = (f"Hoje {'está' if h else 'não está'} dentro do limite de R$ 150 para brindes e presentes. "
             f"Em 2025 {'estaria' if o else 'não estaria'} dentro do limite de R$ 100.")
        S.add("versao", q, [ch(BR_OLD, "## Limites de 2025"), ch(BR_NEW, "## Limites\n")], r, rng, sub="brindes_comparacao")

    # reembolso
    for _ in range(40):
        v = round(rng.uniform(25, 130), 2) if rng.random() < 0.5 else float(rng.randrange(25, 131))
        q = rng.choice([f"Gastei {brl(v)} em uma refeição durante uma viagem a trabalho. Quanto será reembolsado?",
                        f"Almocei por {brl(v)} em deslocamento a trabalho. O reembolso cobre tudo?"])
        r = (f"A refeição de {brl(v)} está dentro do limite de até R$ 70 por refeição e pode ser reembolsada integralmente." if v <= 70 else
             f"O reembolso de refeição é de até R$ 70 por refeição, então dos {brl(v)} gastos serão reembolsados no máximo R$ 70.")
        S.add("faixa_valor", variante(q, rng), [ch(RE_NEW, "## O que é reembolsável")], r, rng, sub="reembolso_refeicao")
    for n in livre(rng, (20, 640), 5, 30):
        q = rng.choice([f"Rodei {n} km com meu carro em uma viagem a trabalho, com aprovação prévia. Quanto recebo?", f"Quanto é reembolsado por {n} km rodados com carro próprio, com aprovação prévia?"])
        r = f"Com aprovação prévia, a quilometragem com carro próprio é reembolsada a R$ 1,20 por km. Para {n} km, o valor é {brl2(n * 1.2)}."
        S.add("aritmetica", variante(q, rng), [ch(RE_NEW, "## O que é reembolsável")], r, rng, checar=False, sub="km")


# ------------------------------------------------------------------ aritmética
UN = {"posição-palete/mês": ("posição-palete", "posições-palete"), "palete": ("palete", "paletes"), "caixa": ("caixa", "caixas"),
      "unidade": ("unidade", "unidades"), "kit": ("kit", "kits"), "km rodado": ("km", "km"), "kg": ("kg", "kg")}


def tabela_trimestral():
    _, corpo = ctxs.chunks(DRE)[0], None
    rows = {}
    for linha in (RAIZ / DRE).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| (\d{4}T\d) \|(.*)\|\s*$", linha)
        if m:
            c = [num_br(x.strip().replace("R$", "").strip()) for x in m.group(2).split("|")]
            rows[m.group(1)] = dict(zip(["rb", "rl", "cmv", "lb", "dop", "ebitda", "rliq"], c))
    return rows


def gerar_aritmetica(S, rng):
    # preço de tabela x quantidade
    servicos = []
    for linha in (RAIZ / PORT).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| ([A-Z]{3}-\d{3}) \| (.+?) \| (.+?) \| R\$ ([\d.,]+) \|", linha)
        if m and m.group(3) in UN:
            servicos.append((m.group(1), m.group(2), m.group(3), num_br(m.group(4))))
    for cod, nome, cob, preco in servicos:
        sing, plur = UN[cob]
        for n in livre(rng, (3, 900), 1, 12):
            if cod in ("ARM-001", "ARM-002") and n in (200, 50):
                continue
            q = rng.choice([f"Quanto custa, pela tabela, {n} {plur} no serviço de {nome.lower()}?",
                            f"Qual o valor de {n} {plur} de {nome.lower()} pelo preço de tabela?"])
            por = sing + (" ao mês" if "/mês" in cob else "")
            r = (f"{nome}, código {cod}, custa {brl2(preco)} por {por}. Para {n} {plur}, o total pela tabela é {brl2(n * preco)}, "
                 f"antes de eventuais descontos.")
            S.add("aritmetica", variante(q, rng), [ch_com(PORT, cod)], r, rng, checar=False, sub="tabela_preco")
    # VR e PLR
    for d in [x for x in range(14, 24) if x != 22]:
        q = rng.choice([f"Trabalhei {d} dias neste mês. Quanto de VR vai cair no cartão?", f"O VR é pago por dia trabalhado. Com {d} dias, qual o crédito do mês?", f"Se eu trabalhar {d} dias no mês, quanto vem de VR?"])
        S.add("aritmetica", variante(q, rng), [ch_com(BEN, "Vale-refeição")], f"O VR é de R$ 42 por dia trabalhado, então {d} dias resultam em {brl(d * 42)}.",
              rng, checar=False, sub="vr")
    for s in livre(rng, (2200, 14000), 100, 30):
        q = rng.choice([f"Com salário de {brl(s)}, qual o valor máximo de PLR que eu poderia receber?", f"Ganho {brl(s)} por mês. Qual o teto do meu PLR?"])
        S.add("aritmetica", variante(q, rng), [ch_com(PLR, "O valor máximo do PLR")],
              f"O PLR paga até 1,5 salário, ou seja, no máximo {brl(s * 1.5)} para um salário de {brl(s)}.", rng, checar=False, sub="plr")
    # DRE
    tri = tabela_trimestral()
    chave = list(tri)
    for _ in range(90):
        a, b = rng.sample(chave, 2)
        if {a, b} == {"2025T1", "2025T2"}:
            continue
        if rng.random() < 0.5:
            q = rng.choice([f"Quanto a receita líquida de {a} e {b} somou no total?", f"Qual a soma das receitas líquidas de {a} e de {b}?"])
            r = f"Somadas, as receitas líquidas de {a} ({brl(tri[a]['rl'])}) e {b} ({brl(tri[b]['rl'])}) totalizam {brl(tri[a]['rl'] + tri[b]['rl'])}."
        else:
            if {a, b} == {"2025T4", "2025T1"}:
                continue
            q = rng.choice([f"Qual a diferença entre o EBITDA de {a} e o de {b}?", f"Quanto o EBITDA de {a} difere do de {b}?"])
            x, y = tri[a]["ebitda"], tri[b]["ebitda"]
            r = f"O EBITDA de {a} foi de {brl(x)} e o de {b} foi de {brl(y)}, uma diferença de {brl(abs(x - y))}, maior em {a if x > y else b}."
        S.add("aritmetica", q, [ch_com(DRE, "| 2024T1")], r, rng, checar=False, sub="dre_trimestral")
    anual = {}
    for linha in (RAIZ / DRE).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| (?:\*\*)?(Receita líquida|Lucro bruto|EBITDA)(?:\*\*)? \| R\$ ([\d.]+) \| R\$ ([\d.]+) \|", linha)
        if m:
            anual[m.group(1)] = {"2024": num_br(m.group(2)), "2025": num_br(m.group(3))}
    for ano in ("2024", "2025"):
        rl = anual["Receita líquida"][ano]
        for nome, k, txt in (("Lucro bruto", "margem bruta", "lucro bruto"), ("EBITDA", "margem EBITDA", "EBITDA")):
            if (ano, k) == ("2025", "margem bruta"):
                continue
            q = rng.choice([f"Em {ano}, que percentual da receita líquida virou {txt}?", f"Quanto foi a {k} da Brisa Log em {ano}?"])
            v = anual[nome][ano]
            r = f"O {txt} de {ano} foi de {brl(v)} sobre uma receita líquida de {brl(rl)}, uma margem de {pct(v / rl * 100, 1)}."
            S.add("aritmetica", q, [ch_com(DRE, "| Receita bruta")], r, rng, checar=False, sub="dre_margem")
    # orçamento
    orc = []
    for linha in (RAIZ / ORC).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| (.+?) \| R\$ ([\d.]+) \| [\d,]+% \|", linha)
        if m:
            orc.append((m.group(1), num_br(m.group(2))))
    for _ in range(30):
        (na, va), (nb, vb) = rng.sample(orc, 2)
        if {na, nb} == {"TI", "Comercial"}:
            continue
        if va < vb:
            na, va, nb, vb = nb, vb, na, va
        q = rng.choice([f"Qual a diferença entre o orçamento de {na} e o de {nb} em 2026?", f"Quanto o orçamento anual de {na} supera o de {nb}?"])
        r = f"O orçamento anual de {na} é de {brl(va)} e o de {nb} é de {brl(vb)}, uma diferença de {brl(va - vb)} a favor de {na}."
        S.add("aritmetica", q, [ch_com(ORC, "Orçamento anual 2026")], r, rng, checar=False, sub="orcamento")


# ------------------------------------------------------------------ versão antiga x nova
VERSOES = [
    ([(HO_OLD, "## O que dizia a regra de 2025"), (HO_NEW, "## Quantos dias")],
     ["Em 2025, quantos dias de home office por semana a empresa permitia, e quantos permite hoje?", "Quantos dias por semana eu podia trabalhar de casa em 2025 e quantos posso agora?",
      "Qual era o limite semanal de home office em 2025 e qual é o atual?"],
     "Em 2025, com a política já revogada, eram 1 dia por semana. A versão 2026, vigente, permite 2 dias por semana."),
    ([(HO_OLD, "## O que dizia a regra de 2025"), (HO_NEW, "## Quantos dias")],
     ["Meu amigo de outra equipe disse que o home office é de 1 dia por semana. Isso ainda vale?", "Li que só se pode trabalhar de casa 1 dia por semana. Está atualizado?",
      "O limite de home office ainda é de 1 dia por semana?"],
     "Não, essa informação está desatualizada. O limite de 1 dia por semana era da política de 2025, revogada. A versão 2026 permite 2 dias por semana."),
    ([(HO_OLD, "## O que dizia a regra de 2025"), (HO_NEW, "## Apoio financeiro")],
     ["Existia auxílio internet em 2025? E hoje, quanto é?", "A empresa pagava auxílio internet para home office em 2025? Quanto paga agora?"],
     "Não. Em 2025 o auxílio internet era de R$ 0, porque não havia pagamento. Na versão 2026 o auxílio é de R$ 100 por mês."),
    ([(HO_OLD, "## O que dizia a regra de 2025"), (HO_NEW, "## Apoio financeiro")],
     ["Qual a ajuda de custo para estrutura de home office hoje e como era em 2025?", "A ajuda para comprar cadeira e mesa existia em 2025? De quanto é agora?"],
     "Em 2025 a ajuda de estrutura era de R$ 0, sem ajuda de custo. Na versão 2026 ela é de R$ 500, paga uma única vez."),
    ([(HO_OLD, "## Por que mudou"), (HO_NEW, "## Quantos dias")],
     ["O que mudou na política de home office de 2025 para 2026?", "Quais foram as diferenças entre a política de home office de 2025 e a de 2026?"],
     "Os dias de home office subiram de 1 para 2 por semana, o auxílio internet passou de R$ 0 para R$ 100 por mês, a ajuda de estrutura passou de R$ 0 para R$ 500 "
     "(pagamento único) e passaram a existir dias presenciais fixos, terça-feira e quarta-feira."),
    ([(RE_OLD, "## Prazos que valiam em 2025"), (RE_NEW, "## Prazos\n")],
     ["Qual o prazo para enviar o pedido de reembolso hoje e qual era em 2025?", "Em 2025 eu tinha quantos dias para pedir reembolso? E agora?"],
     "Em 2025 o pedido devia ser enviado em até 10 dias corridos após a despesa. Hoje, na versão 2026, o prazo é de até 15 dias corridos."),
    ([(RE_OLD, "## Prazos que valiam em 2025"), (RE_NEW, "## Prazos\n")],
     ["O pagamento do reembolso ficou mais rápido ou mais lento em 2026?", "O reembolso hoje é pago mais depressa do que em 2025?"],
     "Ficou mais rápido. Em 2025 o pagamento era feito em até 45 dias após o envio e, na versão 2026, é feito em até 30 dias."),
    ([(RE_OLD, "## Prazos que valiam em 2025"), (RE_NEW, "## Prazos\n")],
     ["Um colega disse que o reembolso é pago em até 45 dias. Está certo?", "Ainda vale o prazo de 45 dias para receber o reembolso?"],
     "Não, essa informação está desatualizada. O prazo de 45 dias era o de 2025, revogado. Hoje o reembolso é pago em até 30 dias após o envio da solicitação completa."),
    ([(BR_OLD, "## O que mudou em 2026"), (BR_NEW, "## Limites\n")],
     ["Qual era o limite para refeições e hospitalidade em 2025 e qual é hoje?", "Em 2025, até quanto podia custar uma refeição oferecida por parceiros, e agora?"],
     "Em 2025 o limite para refeição ou hospitalidade era de R$ 150 por pessoa. Na versão 2026 passou a ser de R$ 200."),
    ([(BR_OLD, "## O que mudou em 2026"), (BR_NEW, "## Limites\n")],
     ["Um parceiro disse que o limite para brindes é de R$ 100. Isso está atualizado?", "O limite de presentes ainda é de R$ 100?"],
     "Não. O limite de R$ 100 era o de 2025, revogado. Hoje o limite para brinde ou presente é de R$ 150 por pessoa."),
    ([(BR_OLD, "## O que mudou em 2026"), (BR_NEW, "## Limites\n")],
     ["O que mudou nos limites de brindes e refeições em 2026?", "Os limites da política de brindes mudaram de 2025 para 2026?"],
     "Os limites subiram: o de brindes e presentes passou de R$ 100 para R$ 150, e o de refeições e hospitalidade passou de R$ 150 para R$ 200. "
     "O prazo de registro, a proibição de dinheiro e a vedação a agentes públicos não mudaram."),
    ([(AL_OLD, "## Tabela de 2025"), (AL_NEW, "## Tabela de alçadas")],
     ["Até quanto o gestor imediato aprovava em 2025 e até quanto aprova hoje?", "Qual era a alçada do gestor em 2025 e qual é a atual?"],
     "Em 2025 o gestor imediato aprovava até R$ 1.000. Na versão 2026, aprova até R$ 2.000."),
    ([(AL_OLD, "## Tabela de 2025"), (AL_NEW, "## Tabela de alçadas")],
     ["Quanto o diretor da área podia aprovar em 2025 e quanto pode agora?", "Qual o limite do diretor em 2025 e qual é o de hoje?"],
     "Em 2025 o diretor da área aprovava acima de R$ 1.000 e até R$ 10.000. Hoje, na versão 2026, aprova acima de R$ 2.000 e até R$ 20.000."),
]


def gerar_versoes(S, rng):
    for trechos, qs, a in VERSOES:
        tr = [ch(r, i) for r, i in trechos]
        for q in qs:
            S.add("versao", variante(q, rng), tr, a, rng, sub="comparacao")
            if rng.random() < 0.7:  # a mesma pergunta em outro estilo
                S.add("versao", informal(q, rng), tr, a, rng, sub="comparacao")


# ------------------------------------------------------------------ multi-documento
def gerar_multidoc(S, rng, n):
    treino_ids = {r["meta"]["fato_id"] for r in ler_jsonl("qa/qa_treino.jsonl") if r["meta"]["tipo"] in ("direta", "com_contexto", "multi_turno")}
    fatos = [f for f in ler_jsonl("fatos/fatos.jsonl") if f["fato_id"] in treino_ids and f["fonte_doc"].endswith(".md")
             and f["sensibilidade"] == "publico"]
    por_area = {}
    for f in fatos:
        por_area.setdefault(f["area"], []).append(f)
    tentativas, feitos = 0, 0
    while feitos < n and tentativas < 20000:
        tentativas += 1
        f = rng.choice(fatos)
        pool = por_area[f["area"]] if rng.random() < 0.6 else fatos
        g = rng.choice(pool)
        if g["fonte_doc"] == f["fonte_doc"] or g["fato_id"] == f["fato_id"]:
            continue
        q1, q2 = f["perguntas"][0], g["perguntas"][1]
        q = rng.choice([f"{q1} E {lower_first(q2)}", f"{q1.rstrip('?')} e, além disso, {lower_first(q2)}", f"Tenho duas dúvidas. {q1} {q2}"])
        trechos = list(ctxs.completos(f)[0])
        for t in ctxs.completos(g)[0]:
            if t not in trechos:
                trechos.append(t)
        r = f"{f['resposta'].rstrip()} {g['resposta'].lstrip()}"
        try:
            if S.add("multi_doc", variante(q, rng) if rng.random() < 0.15 else q, trechos, r, rng, distrator=0.3, fato_ids=[f["fato_id"], g["fato_id"]]):
                feitos += 1
        except AssertionError:
            continue


def main():
    ficha = carregar_ficha()
    rng = random.Random(ficha["empresa"]["seed"] + 31)
    S = Saida()
    gerar_faixas(S, rng)
    gerar_aritmetica(S, rng)
    gerar_versoes(S, rng)
    gerar_multidoc(S, rng, 450)
    extra = S.itens
    rng.shuffle(extra)
    escrever_jsonl("qa/qa_v3_extra.jsonl", extra)
    base = [{"messages": r["messages"]} for r in ler_jsonl("qa/qa_treino.jsonl")]
    todos = base + [{"messages": r["messages"]} for r in extra]
    random.Random(ficha["empresa"]["seed"] + 53).shuffle(todos)
    escrever_jsonl("export/sft_treino_v3.jsonl", todos)
    print("extras:", len(extra), dict(Counter(r["meta"]["tipo"] for r in extra)))
    print("subtipos:", dict(Counter(r["meta"].get("sub") for r in extra if r["meta"].get("sub"))))
    print("descartes:", dict(S.rej))
    print("export/sft_treino_v3.jsonl:", len(todos), "exemplos")


if __name__ == "__main__":
    main()
