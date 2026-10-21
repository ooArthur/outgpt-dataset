"""Gera os CSVs de data/ a partir da ficha-mestra (seed fixa)."""
import datetime as dt
import random

from common import carregar_ficha, escrever_csv, sem_acento

PRIMEIROS = """Adriana Alexandre Aline Amanda Ana André Andressa Antônio Armando Bárbara Bianca Bruno Camila Carla
Carlos Carolina Cássio Cecília Cláudia Clóvis Cristiane Daniel Débora Diego Douglas Edson Elaine Eliane Elisa Emerson
Érica Fábio Felipe Flávia Gabriel Gabriela Gilberto Giovana Gustavo Heitor Helena Henrique Igor Ingrid Isabela Jaqueline
Jéssica João Joaquim Jonas Josiane Juliana Júlio Karina Kleber Larissa Laura Leandro Letícia Lívia Lucas Luan Luísa
Marcelo Márcia Marcos Maria Mariana Mateus Mauro Michele Miguel Mônica Natália Nelson Nicole Olívia Paula Paulo Pedro
Priscila Rafael Rafaela Raquel Renan Renata Rodrigo Rosana Samuel Sandra Sérgio Silvia Simone Sofia Tadeu Tainá Talita
Tatiane Thaís Valdir Vanessa Vera Vinícius Viviane Wellington Yasmin""".split()
SOBRENOMES = """Almeida Andrade Araújo Azevedo Barbosa Batista Borges Brandão Cardoso Carvalho Castro Cavalcanti Correia Costa
Coutinho Dias Duarte Esteves Farias Fernandes Ferreira Figueiredo Fonseca Freitas Gomes Gonçalves Guedes Henriques
Jardim Lacerda Lima Machado Magalhães Marques Martins Mendes Miranda Moraes Moreira Nascimento Neves Nogueira Nunes
Oliveira Pacheco Paiva Pereira Pinto Ramos Ribeiro Rocha Rodrigues Santana Santos Silva Soares Sousa Teixeira
Torres Vasconcelos Vaz Viana Vieira Xavier""".split()

UNIDADES = {"c": "Campinas/SP", "u": "Uberlândia/MG"}


def gerar_funcionarios(ficha, rng):
    usados = {n for blocos in ficha["quadro"].values() for c in blocos for n in c.get("nomes", [])}
    pessoas = []
    for dep in ficha["departamentos"]:
        for cargo in ficha["quadro"][dep["id"]]:
            nomes_fixos = list(cargo.get("nomes", []))
            for un in ("c", "u"):
                for _ in range(cargo["qtd"].get(un, 0)):
                    if nomes_fixos:
                        nome = nomes_fixos.pop(0)
                    else:
                        while True:
                            nome = f"{rng.choice(PRIMEIROS)} {rng.choice(SOBRENOMES)} {rng.choice(SOBRENOMES)}"
                            if nome not in usados and nome.split()[1] != nome.split()[2]:
                                usados.add(nome)
                                break
                    pessoas.append({"nome": nome, "cargo": cargo["cargo"], "dep": dep, "un": un,
                                    "nivel": cargo["nivel"], "reporta": cargo["reporta"]})
    for i, p in enumerate(pessoas, 1):
        p["id"] = i

    # gestor imediato: mesmo cargo-alvo, preferindo a mesma unidade; distribui em rodízio
    contadores = {}
    for p in pessoas:
        if p["reporta"] is None:
            p["gestor_id"] = ""
            continue
        cand = [q for q in pessoas if q["cargo"] == p["reporta"]]
        mesma = [q for q in cand if q["un"] == p["un"]] or cand
        assert mesma, f"gestor não encontrado para {p['cargo']} -> {p['reporta']}"
        k = (p["reporta"], p["un"])
        contadores[k] = contadores.get(k, -1) + 1
        p["gestor_id"] = mesma[contadores[k] % len(mesma)]["id"]

    # admissão, ramal, e-mail
    dominio = ficha["empresa"]["dominio_email"]
    dpo = ficha["encarregado_lgpd"]
    seq_ramal, emails = {}, set()
    for p in pessoas:
        lider = p["nivel"] in ("Diretoria", "Gerência")
        if p["cargo"] == "CEO":
            ini, fim = dt.date(2019, 3, 1), dt.date(2019, 3, 1)
        elif lider:
            ini, fim = dt.date(2013, 1, 7), dt.date(2020, 12, 15)
        else:
            ini = dt.date(2021, 3, 1) if p["un"] == "u" else dt.date(2010, 3, 1)
            fim = dt.date(2026, 9, 14)
        p["admissao"] = (ini + dt.timedelta(days=rng.randint(0, (fim - ini).days))).isoformat()
        base = p["dep"]["ramal_base"] + (1000 if (p["dep"]["id"] == "ops" and p["un"] == "u") else 0)
        seq_ramal[base] = seq_ramal.get(base, 0) + 1
        p["ramal"] = dpo["ramal"] if p["nome"] == dpo["nome"] else base + seq_ramal[base]
        partes = sem_acento(p["nome"]).lower().split()
        email, n = f"{partes[0]}.{partes[-1]}", 1
        while f"{email}@{dominio}" in emails:
            n += 1
            email = f"{partes[0]}.{partes[-1]}{n}"
        emails.add(f"{email}@{dominio}")
        p["email"] = f"{email}@{dominio}"
    return pessoas


def gerar_financeiro(ficha, rng):
    f = ficha["financeiro"]
    linhas = []
    for ano, liquidas in f["receita_liquida_trimestral"].items():
        for i, liq in enumerate(liquidas, 1):
            ded_pct = f["deducoes_pct_da_bruta"] / 100
            ded = round(liq * ded_pct / (1 - ded_pct))
            bruta = liq + ded
            cmv = round(liq * (f["cmv_pct_da_liquida"] + rng.uniform(-0.7, 0.7)) / 100)
            lucro_bruto = liq - cmv
            desp = round(liq * (f["desp_op_pct_da_liquida"] + rng.uniform(-0.6, 0.6)) / 100)
            ebitda = lucro_bruto - desp
            da = f["dep_amort_trimestre"][ano]
            fin = round(liq * (f["resultado_financeiro_pct_da_liquida"] + rng.uniform(-0.15, 0.15)) / 100)
            lair = ebitda - da + fin
            ir = round(lair * f["ir_csll_pct"] / 100) if lair > 0 else 0
            linhas.append({
                "trimestre": f"{ano}T{i}", "receita_bruta": bruta, "deducoes": ded, "receita_liquida": liq,
                "cmv": cmv, "lucro_bruto": lucro_bruto, "despesas_operacionais": desp, "ebitda": ebitda,
                "depreciacao_amortizacao": da, "resultado_financeiro": fin, "ir_csll": ir,
                "resultado_liquido": lair - ir,
            })
    return linhas


def gerar_orcamento(ficha, rng):
    pesos = ficha["orcamento_pesos_trimestre"]
    linhas = []
    for dep in ficha["departamentos"]:
        acumulado = 0
        for t in range(4):
            orc = round(dep["orcamento_2026"] * pesos[t])
            if t == 3:  # fecha o ano exatamente
                orc = dep["orcamento_2026"] - acumulado
            acumulado += orc
            if t < 2:
                real = round(orc * rng.uniform(0.92, 1.06))
                linhas.append({"departamento": dep["nome"], "trimestre": f"2026T{t+1}", "orcado": orc,
                               "realizado": real, "saldo": orc - real, "status": "realizado"})
            else:
                linhas.append({"departamento": dep["nome"], "trimestre": f"2026T{t+1}", "orcado": orc,
                               "realizado": "", "saldo": "", "status": "em_aberto"})
    return linhas


def main():
    ficha = carregar_ficha()
    rng = random.Random(ficha["empresa"]["seed"])

    pessoas = gerar_funcionarios(ficha, rng)
    assert len(pessoas) == ficha["empresa"]["colaboradores"], len(pessoas)
    escrever_csv("data/funcionarios.csv",
                 ["id", "nome", "cargo", "departamento", "gestor_id", "unidade", "data_admissao", "ramal", "email"],
                 [{"id": p["id"], "nome": p["nome"], "cargo": p["cargo"], "departamento": p["dep"]["nome"],
                   "gestor_id": p["gestor_id"], "unidade": UNIDADES[p["un"]], "data_admissao": p["admissao"],
                   "ramal": p["ramal"], "email": p["email"]} for p in pessoas])

    fin = gerar_financeiro(ficha, rng)
    escrever_csv("data/financeiro_trimestral.csv", list(fin[0].keys()), fin)

    orc = gerar_orcamento(ficha, rng)
    escrever_csv("data/orcamento_departamentos_2026.csv",
                 ["departamento", "trimestre", "orcado", "realizado", "saldo", "status"], orc)

    escrever_csv("data/catalogo_servicos.csv",
                 ["codigo", "servico", "categoria", "unidade_cobranca", "preco_unitario_brl", "disponibilidade", "observacao"],
                 [{"codigo": s["codigo"], "servico": s["servico"], "categoria": s["categoria"],
                   "unidade_cobranca": s["unidade_cobranca"], "preco_unitario_brl": f"{s['preco']:.2f}",
                   "disponibilidade": s["disponibilidade"], "observacao": s["observacao"]}
                  for s in ficha["catalogo_servicos"]])
    print(f"data/: {len(pessoas)} funcionários, {len(fin)} trimestres, {len(orc)} linhas de orçamento, "
          f"{len(ficha['catalogo_servicos'])} serviços")


if __name__ == "__main__":
    main()
