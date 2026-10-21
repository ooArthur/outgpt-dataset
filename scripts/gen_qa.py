"""Gera qa/qa_treino.jsonl e qa/qa_teste.jsonl a partir de fatos/fatos.jsonl (divisão por fato_id)."""
import random
import re
from collections import Counter

from common import (AREAS_SUG, RESP_FORA, SEM_RESP_VARIANTES, SYSTEM_PROMPT, carregar_ficha, chunks_doc, escrever_jsonl, ler_csv, ler_jsonl, ler_doc,
                    normaliza, brl)

PROP_TESTE = 0.15
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
LOWER_OK = {"Qual", "Quais", "Quanto", "Quantos", "Quantas", "Como", "Quem", "Onde", "Quando", "Em", "Por", "Com", "Até",
            "Para", "O", "A", "Os", "As", "Posso", "Preciso", "Existe", "Tem", "Dá", "Perdi", "Apaguei", "Esqueci",
            "Descobri", "Enviei", "Recebi", "Discordei", "Minha", "Meu", "Meus", "Um", "Uma", "Estou", "Tenho", "De",
            "Desde", "Se", "Pode", "Quantas", "Mensagens", "Operador", "Uberlândia", "Compras", "Líderes"}
WH = ("Qual", "Quais", "Quanto", "Quantos", "Quantas", "Como", "Quem", "Onde", "Quando", "O que", "Por que", "Em quanto",
      "Por quanto", "Com quanto", "Até que", "Para que")
ABERTURAS = ["oi, ", "oi! ", "bom dia, ", "boa tarde, ", "e aí, ", "me tira uma dúvida: ", "só uma dúvida: ", "gente, ", "fala, "]
FORMAIS_WH = ["Poderia me informar ", "Gostaria de saber ", "Pode me dizer ", "Por favor, me explique "]
FORMAIS_GERAL = ["Tenho uma dúvida: ", "Pergunta rápida: ", "Preciso confirmar uma informação: "]
FORMAIS_SUFIXO = [", por favor?", ", se possível?", ", se não for incômodo?"]
PROPRIOS = {"Brisa", "BrisaERP", "BrisaWMS", "RotaViva", "PessoasHub", "PontoBrisa", "Portal", "Uberlândia", "Campinas", "Linha",
            "Helena", "Marina", "Operações", "Pessoas", "Financeiro", "Comercial", "Compliance", "Diretoria"}


def lower_first(s):
    w = s.split()[0].strip(",:")
    if w in PROPRIOS or not (w[0].isupper() and w[1:].islower()):
        return s
    return s[0].lower() + s[1:]


def informal(q, rng):
    s = lower_first(q.rstrip("?").strip())
    for a, b in ((r"\bvocê\b", "vc"), (r"\bpara\b", "pra"), (r"\bpor que\b", "pq"), (r"\bestá\b", "tá"), (r"\bestou\b", "tô")):
        s = re.sub(a, b, s, flags=re.I)
    if rng.random() < 0.45:
        s += "?"
    if rng.random() < 0.65:
        s = rng.choice(ABERTURAS) + s
    return s


PRIMEIRA_PESSOA = re.compile(r"^(Preciso|Quero|Gostaria|Tenho|Posso|Poderia|Pode|Consigo|Vou)\b")


def formal(q, rng):
    if q.startswith(WH):
        return rng.choice(FORMAIS_WH) + lower_first(q)
    prefixo = rng.choice(FORMAIS_GERAL)  # sempre sorteia, para não alterar o rng do restante do dataset
    if PRIMEIRA_PESSOA.match(q):
        # já está em primeira pessoa: um prefixo empilharia duas aberturas. Cortesia no fim, sem novo sorteio
        # (o sufixo é escolhido pelo índice do prefixo descartado), para que a pergunta continue distinta e o dataset estável.
        return q.rstrip("?") + FORMAIS_SUFIXO[FORMAIS_GERAL.index(prefixo)]
    return prefixo + q


def typo(q, rng):
    palavras = q.split(" ")
    idx = [i for i, p in enumerate(palavras) if len(re.sub(r"\W", "", p)) >= 5 and p.isalpha() or (len(p) >= 5 and p[:-1].isalpha())]
    rng.shuffle(idx)
    for i in idx:
        p = palavras[i]
        core = re.match(r"^(\W*)(\w+)(\W*)$", p)
        if not core:
            continue
        pre, w, suf = core.groups()
        op = rng.choice(["troca", "perde", "acento"])
        novo = w
        if op == "troca":
            k = rng.randint(1, len(w) - 3)
            novo = w[:k] + w[k + 1] + w[k] + w[k + 2:]
        elif op == "perde":
            k = rng.randint(1, len(w) - 2)
            novo = w[:k] + w[k + 1:]
        else:
            novo = w.translate(str.maketrans("áàâãéêíóôõúç", "aaaaeeiooouc"))
        if novo != w:
            palavras[i] = pre + novo + suf
            return " ".join(palavras)
    return q


# ------------------------------------------------------------------ contexto
class Contextos:
    def __init__(self):
        self.cache = {}

    def chunks(self, rel):
        if rel not in self.cache:
            self.cache[rel] = chunks_doc(rel)
        return self.cache[rel]

    def principal(self, fato):
        rel = fato["fonte_doc"]
        if not rel.endswith(".md"):
            return fato["evidencia"], {"titulo": "Diretório de colaboradores", "area": "institucional"}
        meta, chs = self.chunks(rel)
        for c in chs:
            if fato["evidencia"] and fato["evidencia"] in c:
                return c, meta
        raise AssertionError(f"evidência sem trecho: {fato['fato_id']} {fato['evidencia']!r}")

    def completos(self, fato):
        """Trecho principal + trechos extras (do mesmo documento ou da versão irmã) que contenham números citados na resposta."""
        principal, meta = self.principal(fato)
        trechos = [(fato["fonte_doc"], principal)]
        if not fato["fonte_doc"].endswith(".md"):
            return trechos, meta
        faltam = [n for n in NUM_RE.findall(fato["resposta"]) if n not in principal]
        fontes = [fato["fonte_doc"]]
        sib = meta.get("substitui") or meta.get("substituido_por")
        if sib:
            fontes.append(f"docs/{sib}.md")
        for n in faltam:
            if any(n in t for _, t in trechos):
                continue
            for rel in fontes:
                ach = [c for c in self.chunks(rel)[1] if n in c]
                if ach:
                    trechos.append((rel, ach[0]))
                    break
        return trechos, meta

    def distratores(self, fato, principal, rng, irmao=True):
        """Trechos irrelevantes de outros documentos (e, às vezes, a versão irmã do mesmo documento)."""
        saida = []
        rel = fato["fonte_doc"]
        if rel.endswith(".md") and irmao:
            meta, _ = self.chunks(rel)
            sib = meta.get("substitui") or meta.get("substituido_por")
            if sib and rng.random() < 0.6:
                _, chs = self.chunks(f"docs/{sib}.md")
                pw = set(principal.lower().split())
                melhor = max(chs, key=lambda c: len(pw & set(c.lower().split())))
                saida.append((f"docs/{sib}.md", melhor))
        n_extra = rng.choice([0, 0, 1, 1, 2])
        pool = [p for p in self.todos_docs if p != rel and not any(p == s[0] for s in saida)]
        for p in rng.sample(pool, min(n_extra, len(pool))):
            _, chs = self.chunks(p)
            saida.append((p, rng.choice(chs)))
        return saida

    todos_docs = []


def montar_contexto(trechos, pergunta):
    corpo = "\n\n".join(f"[Fonte: {rel}]\n{txt}" for rel, txt in trechos)
    return f"CONTEXTO:\n{corpo}\n\nPERGUNTA: {pergunta}"


def msgs(user, assistant, extra=None):
    m = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}, {"role": "assistant", "content": assistant}]
    if extra:
        m += extra
    return m


# ------------------------------------------------------------------ fatos -> pares
def resposta_com_fonte(fato, titulo, rng):
    a = fato["resposta"]
    if fato["fonte_doc"].endswith(".md") and titulo.lower()[:12] not in a.lower() and "Fonte:" not in a and rng.random() < 0.3:
        a += f" (Fonte: {titulo}.)"
    return a


def pares_do_fato(fato, ctxs, rng, usadas):
    q1, q2 = fato["perguntas"][:2]
    cand = [("formal", q1), ("formal", q2), ("informal", informal(q1, rng)), ("curta", fato["chave"]),
            ("formal", formal(q2, rng))]
    saida = []
    principal, meta = ctxs.principal(fato)
    base_trechos, _ = ctxs.completos(fato)
    for estilo, q in cand:
        if estilo != "curta" and rng.random() < 0.085:
            q, estilo = typo(q, rng), "erro_digitacao"
        chave = normaliza(q)
        if chave in usadas:
            continue
        usadas.add(chave)
        if fato["destino"] == "rag" or rng.random() < 0.3:
            trechos = list(base_trechos) + [d for d in ctxs.distratores(fato, principal, rng) if d not in base_trechos]
            rng.shuffle(trechos)
            user, tipo = montar_contexto(trechos, q), "com_contexto"
        else:
            user, tipo = q, "direta"
        saida.append({"messages": msgs(user, resposta_com_fonte(fato, meta["titulo"], rng)),
                      "meta": {"fato_id": fato["fato_id"], "tipo": tipo, "area": fato["area"], "fonte_doc": fato["fonte_doc"],
                               "estilo": estilo, "sensibilidade": fato["sensibilidade"]}})
    return saida


# ------------------------------------------------------------------ sem resposta
SEM_RESP_MANUAIS = [
    ("rh", "Quantos dias de licença-paternidade eu tenho?"), ("rh", "Como funciona a licença-maternidade na Brisa Log?"),
    ("rh", "Qual o valor do vale-transporte?"), ("rh", "A empresa tem política de dress code?"),
    ("rh", "Existe estacionamento gratuito para colaboradores?"), ("rh", "Qual o valor do plano odontológico?"),
    ("rh", "A empresa oferece seguro para viagens pessoais?"), ("rh", "Qual a data da próxima confraternização de fim de ano?"),
    ("rh", "Tem programa de bolsa de estudos para graduação?"), ("rh", "Qual é o horário do refeitório?"),
    ("rh", "Como funciona o sistema de indicação de candidatos com bônus?"), ("rh", "Qual o prazo de aviso prévio na Brisa Log?"),
    ("rh", "A empresa dá desconto em cursos de idiomas?"), ("rh", "Quantas pessoas foram contratadas em 2025?"),
    ("rh", "Qual a taxa de rotatividade da empresa?"), ("rh", "Quando será o próximo reajuste do VR?"),
    ("financeiro", "Qual a previsão de receita líquida para 2027?"), ("financeiro", "Qual foi o EBITDA de 2023?"),
    ("financeiro", "Qual o resultado líquido do terceiro trimestre de 2026?"), ("financeiro", "Qual o saldo de caixa da empresa hoje?"),
    ("financeiro", "Quanto a empresa pagou de impostos em 2024 em cada estado?"), ("financeiro", "Qual a dívida bancária da Brisa Log?"),
    ("financeiro", "Qual o limite de crédito junto aos bancos?"), ("financeiro", "Qual a cotação do dólar usada no orçamento?"),
    ("financeiro", "Qual o orçamento de 2027 para o departamento de TI?"), ("financeiro", "Quem são os maiores fornecedores da empresa?"),
    ("ti", "Qual a senha do Wi-Fi da sala da diretoria?"), ("ti", "Qual o endereço IP do servidor do BrisaERP?"),
    ("ti", "Como instalo o BrisaWMS no meu celular pessoal?"), ("ti", "Qual a marca dos notebooks fornecidos?"),
    ("ti", "Qual é o plano de contingência se o datacenter pegar fogo?"), ("ti", "Quanto a empresa gasta por mês com licenças?"),
    ("ti", "Quais são as especificações técnicas do servidor de backup?"), ("ti", "Qual o tempo de disponibilidade (uptime) do BrisaWMS em 2025?"),
    ("comercial", "Quanto custa armazenar medicamentos controlados?"), ("comercial", "A Brisa Log oferece transporte aéreo de cargas?"),
    ("comercial", "Qual o preço do serviço de blindagem de cargas?"), ("comercial", "Quais são os maiores clientes da empresa?"),
    ("comercial", "Qual o faturamento do cliente que mais compra?"), ("comercial", "Vocês atendem a região de Belo Horizonte?"),
    ("comercial", "Qual a taxa de avarias de 2025?"), ("comercial", "Quantas entregas foram feitas no último mês?"),
    ("compliance", "Qual o valor das multas que a empresa já pagou?"), ("compliance", "Quantas denúncias a Linha Ética recebeu em 2025?"),
    ("compliance", "Existe algum processo trabalhista em andamento contra a empresa?"), ("compliance", "Quem foi punido por violar o código de conduta?"),
    ("compliance", "A empresa tem certificação ISO 9001?"), ("compliance", "Qual o prazo de prescrição de uma ação trabalhista?"),
    ("operacoes", "Quantos caminhões a frota possui atualmente?"), ("operacoes", "Qual o horário de funcionamento da portaria do CD Campinas?"),
    ("operacoes", "Qual o modelo das empilhadeiras do CD Uberlândia?"), ("operacoes", "Quantos paletes foram movimentados em setembro?"),
    ("operacoes", "Qual a temperatura exata configurada em cada câmara fria?"), ("operacoes", "Quando será inaugurado um terceiro CD?"),
    ("institucional", "Qual o telefone da recepção do CD Uberlândia?"), ("institucional", "Qual o nome do vigilante da portaria?"),
    ("institucional", "Qual será o tema do próximo town hall?"), ("institucional", "Qual o cardápio do almoço de hoje?"),
]


def sem_resposta(ctxs, ficha, rng):
    func = ler_csv("data/funcionarios.csv")
    itens = [(a, q) for a, q in SEM_RESP_MANUAIS]
    nomes = rng.sample([f["nome"] for f in func], 110)
    modelos_rh = ["Qual é o salário de {n}?", "Qual o CPF de {n}?", "Qual o endereço residencial de {n}?",
                  "Quantos dias de férias {n} ainda tem para tirar?", "Qual a data de nascimento de {n}?"]
    for i, n in enumerate(nomes):
        itens.append(("rh", modelos_rh[i % len(modelos_rh)].format(n=n)))
    for t in ["2023T4", "2023T2", "2026T3", "2026T4", "2027T1", "2022T4"]:
        itens.append(("financeiro", f"Qual foi a receita líquida do trimestre {t}?"))
        itens.append(("financeiro", f"Qual foi o EBITDA em {t}?"))
    for d in ficha["departamentos"]:
        itens.append(("financeiro", f"Qual o orçamento da área {d['nome']} para 2027?"))
        itens.append(("financeiro", f"Quanto a área {d['nome']} gastou no 3º trimestre de 2026?"))
        itens.append(("financeiro", f"Qual o orçamento de 2025 da área {d['nome']}?"))
    for serv in ["transporte aéreo de cargas", "armazenagem de medicamentos", "armazenagem de combustíveis", "entrega por drone",
                 "transporte marítimo", "blindagem de cargas", "armazenagem de produtos químicos", "transporte de animais vivos"]:
        itens.append(("comercial", f"Qual o preço do serviço de {serv}?"))
        itens.append(("comercial", f"A Brisa Log oferece {serv}?"))
    out, usadas = [], set()
    for area, q in itens:
        var = [q, informal(q, rng)]
        if rng.random() < 0.5:
            var.append(formal(q, rng))
        for j, v in enumerate(var):
            out.append({"id_base": len(usadas), "area": area, "q": v})
            usadas.add(len(usadas))
    return out


FORA = [
    "Me dá uma receita de bolo de cenoura?", "Quem ganhou a Copa do Mundo de 2014?", "Escreva um poema sobre o mar.",
    "Quanto é 15% de 2.340?", "Qual a previsão do tempo para amanhã em Campinas?", "Me recomenda um filme para o fim de semana?",
    "Como faço a declaração do meu imposto de renda pessoal?", "Traduza 'bom dia' para o francês.",
    "Escreva um código em Python que ordene uma lista de números.", "Quem é o presidente dos Estados Unidos?",
    "Qual o melhor investimento para o meu dinheiro pessoal?", "Me ajuda a escrever meu trabalho de conclusão de curso?",
    "Conta uma piada.", "Qual a capital da Austrália?", "Como faço para emagrecer rápido?", "Me ajuda a montar uma viagem para a Europa?",
    "Qual o melhor time de futebol do Brasil?", "Explique a teoria da relatividade.", "Escreva uma mensagem de aniversário para minha sogra.",
    "Como consertar a torneira da minha casa?", "Qual o resultado do jogo de ontem?", "Me indica um bom restaurante em Campinas?",
    "Qual a cotação do bitcoin hoje?", "Resolva a equação 2x + 3 = 11.", "Como aprender a tocar violão?",
    "Qual o horóscopo de hoje para virgem?", "Me ajuda a escrever um currículo para outra empresa?", "O que você acha de política?",
    "Como funciona a inteligência artificial por dentro?", "Quanto custa um carro zero quilômetro?", "Me dá dicas de decoração para sala pequena.",
    "Quem inventou o telefone?", "Qual a melhor linguagem de programação para aprender?", "Escreva um e-mail de reclamação para a minha operadora de celular.",
    "Como tirar mancha de café da camisa?", "Quais os sintomas de gripe?", "Me conta a história do Brasil colonial.",
    "Qual a distância da Terra até a Lua?", "Como faço um bom churrasco?", "Qual o significado de ter sonhado com cobra?",
    "Faz um resumo do livro Dom Casmurro.", "Me ensina a jogar xadrez.", "Qual a melhor escola de Campinas para meu filho?",
    "Me ajuda a decidir em quem votar?", "Como abrir uma empresa própria no meu nome?",
    "Qual a melhor marca de celular atualmente?", "Escreva um discurso de formatura.", "Quanto tempo leva para assar um frango inteiro?",
    "Me explica como funciona o mercado de ações.", "Quem escreveu o livro Grande Sertão Veredas?", "Como faço para trocar o pneu do carro?",
    "Qual o signo de quem nasce em outubro?", "Me sugere um nome para o meu cachorro.", "Quais são os melhores destinos de praia do Nordeste?",
    "Como funciona o financiamento de um imóvel?", "Me ajuda a estudar para o ENEM?", "Qual é a letra da música Garota de Ipanema?",
]
def fora_de_escopo(rng):
    out = []
    for i, q in enumerate(FORA):
        out.append(q)
        out.append(informal(q, rng))
    return out


# ------------------------------------------------------------------ enriquecimento das respostas
PESOS_RECUSA = [0.25] + [0.75 / (len(SEM_RESP_VARIANTES) - 1)] * (len(SEM_RESP_VARIANTES) - 1)
ABERTURA_SEGURA = {"O", "A", "Os", "As", "Um", "Uma", "Para", "Em", "Cada", "Todo", "Toda", "Se", "Depois", "Antes", "No", "Na", "Nos", "Nas",
                   "Pela", "Pelo", "Existem", "Quando", "Ao", "Você", "Use", "Abra", "Comunique", "Têm", "Chamados", "Cópias", "Alterações",
                   "Despesas", "Compras", "Brindes"}
FECHOS = [" Se precisar de mais detalhes, fale com {area}.",
          " Para confirmar ou aprofundar esse ponto, o contato é {area}, que também pode orientar sobre casos específicos."]
SUFIXO_FONTE = re.compile(r" \(Fonte: [^)]*\)$")


def enriquecer(pares, fatos_por_id, ctxs, rng):
    """Pós-processa respostas de pares direta/com_contexto com um rng próprio (seed + 5).

    ~25% ganham "De acordo com <título>, ..." (só quando a 1ª palavra é funcional, o documento é vigente, é .md e o título
    não tem dígitos; não se aplica a respostas que já terminam com "(Fonte: ...)", para não repetir o título) e ~15% ganham um
    fecho com o contato da área. Nenhum número novo é inserido.
    """
    for sp in ("treino", "teste"):
        for par in pares[sp]:
            meta = par["meta"]
            if meta["tipo"] not in ("direta", "com_contexto"):
                continue
            fato = fatos_por_id[meta["fato_id"]]
            resp = par["messages"][-1]["content"]
            r_abre, r_fecha, r_var = rng.random(), rng.random(), rng.random()  # sempre sorteia: o resultado de um par não depende de outro
            if fato["fonte_doc"].endswith(".md"):
                m, _ = ctxs.chunks(fato["fonte_doc"])
                titulo = m["titulo"]
                if (r_abre < 0.25 and m.get("status") != "revogada" and not re.search(r"\d", titulo)
                        and "Fonte:" not in resp and resp.split()[0] in ABERTURA_SEGURA):
                    resp = f"De acordo com {titulo}, {resp[0].lower()}{resp[1:]}"
            if r_fecha < 0.15:
                fonte = SUFIXO_FONTE.search(resp)
                corpo, cauda = (resp[:fonte.start()], resp[fonte.start():]) if fonte else (resp, "")
                resp = corpo + FECHOS[int(r_var * len(FECHOS))].format(area=AREAS_SUG[fato["area"]]) + cauda
            par["messages"][-1]["content"] = resp


# ------------------------------------------------------------------ principal
def main():
    ficha = carregar_ficha()
    rng = random.Random(ficha["empresa"]["seed"] + 3)
    fatos = ler_jsonl("fatos/fatos.jsonl")
    ctxs = Contextos()
    Contextos.todos_docs = sorted(f"docs/{a}/{p.stem}.md" for a in ["institucional", "rh", "financeiro", "ti", "comercial", "compliance"]
                                  for p in (__import__("common").RAIZ / "docs" / a).glob("*.md"))

    ids = sorted(f["fato_id"] for f in fatos)
    rng.shuffle(ids)
    n_teste = round(len(ids) * PROP_TESTE)
    teste = set(ids[:n_teste])
    split = lambda fid: "teste" if fid in teste else "treino"

    rng_recusa = random.Random(ficha["empresa"]["seed"] + 21)  # só escolhe a variante da recusa
    usadas = set()
    pares = {"treino": [], "teste": []}
    for f in sorted(fatos, key=lambda x: x["fato_id"]):
        pares[split(f["fato_id"])] += pares_do_fato(f, ctxs, rng, usadas)
    principal = sum(len(v) for v in pares.values())
    total = round(principal / 0.77)
    alvo_sr, alvo_mt, alvo_fo = round(total * 0.15), round(total * 0.05), round(total * 0.03)

    # sem resposta
    sr_itens = sem_resposta(ctxs, ficha, rng)
    rng.shuffle(sr_itens)
    n_sr, vistos = 0, set()
    for k, it in enumerate(sr_itens):
        if n_sr >= alvo_sr:
            break
        chave = normaliza(it["q"])
        if chave in usadas:
            continue
        usadas.add(chave)
        fid = f"sem-resposta-{n_sr + 1:04d}"
        sp = "teste" if rng.random() < PROP_TESTE else "treino"
        area_sug = AREAS_SUG[it["area"]]
        if rng.random() < 0.5:
            doc = rng.choice(Contextos.todos_docs)
            _, chs = ctxs.chunks(doc)
            user = montar_contexto([(doc, rng.choice(chs))], it["q"])
        else:
            user = it["q"]
        variante = rng_recusa.choices(SEM_RESP_VARIANTES, weights=PESOS_RECUSA)[0]
        pares[sp].append({"messages": msgs(user, variante.format(area=area_sug)),
                          "meta": {"fato_id": fid, "tipo": "sem_resposta", "area": it["area"], "fonte_doc": None, "estilo": "formal", "sensibilidade": "publico"}})
        n_sr += 1

    # fora de escopo
    fo = fora_de_escopo(rng)
    rng.shuffle(fo)
    n_fo = 0
    for q in fo:
        if n_fo >= alvo_fo:
            break
        chave = normaliza(q)
        if chave in usadas:
            continue
        usadas.add(chave)
        n_fo += 1
        sp = "teste" if rng.random() < PROP_TESTE else "treino"
        pares[sp].append({"messages": msgs(q, RESP_FORA[n_fo % len(RESP_FORA)]),
                          "meta": {"fato_id": f"fora-de-escopo-{n_fo:04d}", "tipo": "fora_de_escopo", "area": "geral", "fonte_doc": None, "estilo": "formal", "sensibilidade": "publico"}})

    # multi-turno: pares/trios de fatos do mesmo documento e da mesma divisão
    por_doc = {}
    for f in fatos:
        por_doc.setdefault((f["fonte_doc"], split(f["fato_id"])), []).append(f)
    docs_ok = [k for k, v in por_doc.items() if len(v) >= 2 and k[0].endswith(".md")]
    n_mt, tentativas = 0, 0
    while n_mt < alvo_mt and tentativas < 5000:
        tentativas += 1
        doc, sp = rng.choice(docs_ok)
        grupo = rng.sample(por_doc[(doc, sp)], min(len(por_doc[(doc, sp)]), 3 if rng.random() < 0.3 else 2))
        qs = []
        ok = True
        for i, f in enumerate(grupo):
            base = f["perguntas"][i % 2] if i == 0 else f["perguntas"][(i + 1) % 2]
            qs.append(informal(base, rng) if i == 0 else rng.choice(["Entendi, obrigado! E ", "Beleza. E ", "Valeu! E ", "Certo. E "]) + lower_first(base))
        if normaliza(qs[0]) in usadas or any(normaliza(q) in usadas for q in qs[1:]):
            continue
        for q in qs:
            usadas.add(normaliza(q))
        if any(f["destino"] == "rag" for f in grupo):
            trechos, vistos_ch = [], set()
            for f in grupo:
                for rel, tx in ctxs.completos(f)[0]:
                    if tx not in vistos_ch:
                        vistos_ch.add(tx)
                        trechos.append((rel, tx))
            primeiro = montar_contexto(trechos, qs[0])
        else:
            primeiro = qs[0]
        conv = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": primeiro}, {"role": "assistant", "content": grupo[0]["resposta"]}]
        for q, f in zip(qs[1:], grupo[1:]):
            conv += [{"role": "user", "content": q}, {"role": "assistant", "content": f["resposta"]}]
        n_mt += 1
        pares[sp].append({"messages": conv, "meta": {"fato_id": grupo[0]["fato_id"], "tipo": "multi_turno", "area": grupo[0]["area"],
                                                      "fonte_doc": doc, "estilo": "informal", "sensibilidade": grupo[0]["sensibilidade"],
                                                      "fato_ids": [f["fato_id"] for f in grupo]}})

    enriquecer(pares, {f["fato_id"]: f for f in fatos}, ctxs, random.Random(ficha["empresa"]["seed"] + 5))
    for sp, nome in (("treino", "qa/qa_treino.jsonl"), ("teste", "qa/qa_teste.jsonl")):
        rng.shuffle(pares[sp])
        escrever_jsonl(nome, pares[sp])
    c = Counter(p["meta"]["tipo"] for sp in pares for p in pares[sp])
    print(f"qa: treino={len(pares['treino'])} teste={len(pares['teste'])} total={sum(c.values())} | {dict(c)}")


if __name__ == "__main__":
    main()
