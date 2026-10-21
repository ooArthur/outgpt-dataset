"""Gera fatos/fatos.jsonl: fatos escritos à mão (templates/fatos/*.fatos) + fatos programáticos dos CSVs."""
import random
import re
from pathlib import Path

from jinja2 import Environment, StrictUndefined

from common import (linha_diretorio, RAIZ, brl, brl2, carregar_ficha, chunks_doc, escrever_jsonl, ler_csv, ler_doc, num, slug)
from render_docs import contexto

DESTINO = {"ft": "finetuning", "rag": "rag"}
TRI_TXT = {"1": "1º", "2": "2º", "3": "3º", "4": "4º"}


def tri_txt(t):
    return f"{TRI_TXT[t[-1]]} trimestre de {t[:4]}"


def parse_fatos(arquivo, env, ctx):
    texto = arquivo.read_text(encoding="utf-8")
    fatos = []
    for bloco in re.split(r"\n\s*\n", texto.strip()):
        linhas = [l for l in bloco.splitlines() if l.strip() and not l.startswith("#")]
        if not linhas:
            continue
        m = re.match(r"\[(.+?)\]\s+(ft|rag)$", linhas[0].strip())
        assert m, f"{arquivo.name}: cabeçalho inválido: {linhas[0]!r}"
        reg = {"doc": m.group(1), "destino": DESTINO[m.group(2)], "q": [], "e": []}
        for l in linhas[1:]:
            k, _, v = l.partition(": ")
            v = env.from_string(v).render(**ctx).strip()
            if k == "Q":
                reg["q"].append(v)
            elif k == "E":
                reg["e"].append(v)
            elif k in ("F", "K", "A"):
                reg[k.lower()] = v
            else:
                raise AssertionError(f"{arquivo.name}: campo desconhecido {k!r}")
        assert all(c in reg for c in ("f", "a", "k")) and len(reg["q"]) >= 2, f"bloco incompleto: {bloco[:80]}"
        fatos.append(reg)
    return fatos


NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")


def verificar(reg, meta, corpo):
    """Evidência no documento e números do fato presentes na resposta/evidência."""
    erros = []
    for ev in reg["e"]:
        if ev not in corpo:
            erros.append(f"evidência ausente em {reg['doc']}: {ev!r}")
    base = reg["a"] + " " + " ".join(reg["e"]) + " " + str(meta.get("titulo", ""))
    for n in NUM_RE.findall(reg["f"]):
        if n not in base:
            erros.append(f"número {n!r} do fato não aparece na resposta/evidência: {reg['f'][:70]!r}")
    return erros


def fatos_manuais(ficha, ctx):
    env = Environment(undefined=StrictUndefined)
    saida, erros, contadores = [], [], {}
    for arq in sorted((RAIZ / "templates" / "fatos").glob("*.fatos")):
        for reg in parse_fatos(arq, env, ctx):
            rel = f"docs/{reg['doc']}.md"
            meta, corpo = ler_doc(rel)
            erros += verificar(reg, meta, corpo)
            area, nome = reg["doc"].split("/")
            base = f"{area}-{nome}"
            contadores[base] = contadores.get(base, 0) + 1
            saida.append({
                "fato_id": f"{base}-{contadores[base]:02d}", "area": area, "fato": reg["f"], "fonte_doc": rel,
                "destino": reg["destino"], "sensibilidade": meta["acesso"], "perguntas": reg["q"],
                "chave": reg["k"], "resposta": reg["a"], "evidencia": reg["e"][0] if reg["e"] else "",
            })
    assert not erros, "\n".join(erros)
    return saida


# ----------------------------------------------------------------- programáticos
METRICAS = [  # coluna, artigo+nome, verbo, nome-curto
    ("receita_bruta", "a receita bruta", "foi", "receita bruta"),
    ("receita_liquida", "a receita líquida", "foi", "receita líquida"),
    ("lucro_bruto", "o lucro bruto", "foi", "lucro bruto"),
    ("cmv", "o CMV", "foi", "CMV"),
    ("despesas_operacionais", "as despesas operacionais", "foram", "despesas operacionais"),
    ("ebitda", "o EBITDA", "foi", "EBITDA"),
    ("resultado_liquido", "o resultado líquido", "foi", "resultado líquido"),
]


def cap(s):
    return s[0].upper() + s[1:]


def fatos_financeiro():
    rows = ler_csv("data/financeiro_trimestral.csv")
    rel = "docs/financeiro/resumo-dre.md"
    out = []
    for r in rows:
        t = r["trimestre"]
        for col, art, verbo, curto in METRICAS:
            val = int(r[col])
            linha = next(l for l in ler_doc(rel)[1].splitlines() if l.startswith(f"| {t} |"))
            out.append({
                "fato_id": f"financeiro-dre-{t.lower()}-{col.replace('_', '-')}", "area": "financeiro",
                "fato": f"{cap(art)} da Brisa Log no {tri_txt(t)} {verbo} de {brl(val)}.", "fonte_doc": rel,
                "destino": "rag", "sensibilidade": "financeiro_restrito",
                "perguntas": [f"{'Qual foi' if verbo == 'foi' else 'Quais foram'} {art} da Brisa Log no {tri_txt(t)}?",
                              f"Quanto {verbo} {art} da empresa em {t}?"],
                "chave": f"{curto} {t}", "resposta": f"{cap(art)} da Brisa Log no {tri_txt(t)} {verbo} de {brl(val)}, segundo o resumo da DRE (documento de acesso restrito).",
                "evidencia": linha,
            })
    return out


def fatos_orcamento(ficha):
    rows = ler_csv("data/orcamento_departamentos_2026.csv")
    rel = "docs/financeiro/orcamento-departamentos.md"
    out = []
    for d in ficha["departamentos"]:
        linhas = [r for r in rows if r["departamento"] == d["nome"]]
        nome = d["nome"]
        anual = sum(int(r["orcado"]) for r in linhas)
        t1, t2 = linhas[0], linhas[1]
        saldo1s = int(t1["saldo"]) + int(t2["saldo"])
        ev_anual = f"| {nome} | {brl(anual)} |"
        ev_t1 = f"| 2026T1 | {brl(t1['orcado'])} | {brl(t1['realizado'])} | {brl(t1['saldo'])} |"
        ev_t2 = f"| 2026T2 | {brl(t2['orcado'])} | {brl(t2['realizado'])} | {brl(t2['saldo'])} |"
        itens = [
            ("anual", f"O orçamento anual de 2026 da área {nome} é de {brl(anual)}.",
             [f"Qual é o orçamento de 2026 da área {nome}?", f"Quanto a área {nome} tem de orçamento anual em 2026?"],
             f"orçamento anual {nome}", f"O orçamento anual de 2026 da área {nome} é de {brl(anual)}, conforme o documento de orçamento por departamento.", ev_anual),
            ("orcado-t1", f"O orçado da área {nome} em 2026T1 foi de {brl(t1['orcado'])}.",
             [f"Qual foi o valor orçado para {nome} no 1º trimestre de 2026?", f"Quanto estava orçado para a área {nome} em 2026T1?"],
             f"orçado 2026T1 {nome}", f"O valor orçado para a área {nome} no 1º trimestre de 2026 foi de {brl(t1['orcado'])}.", ev_t1),
            ("realizado-t1", f"O realizado da área {nome} em 2026T1 foi de {brl(t1['realizado'])}.",
             [f"Quanto a área {nome} gastou no 1º trimestre de 2026?", f"Qual foi o realizado de {nome} em 2026T1?"],
             f"realizado 2026T1 {nome}", f"A área {nome} realizou {brl(t1['realizado'])} no 1º trimestre de 2026, contra {brl(t1['orcado'])} orçados (saldo de {brl(t1['saldo'])}).", ev_t1),
            ("realizado-t2", f"O realizado da área {nome} em 2026T2 foi de {brl(t2['realizado'])}.",
             [f"Quanto a área {nome} gastou no 2º trimestre de 2026?", f"Qual foi o realizado de {nome} em 2026T2?"],
             f"realizado 2026T2 {nome}", f"A área {nome} realizou {brl(t2['realizado'])} no 2º trimestre de 2026, contra {brl(t2['orcado'])} orçados (saldo de {brl(t2['saldo'])}).", ev_t2),
            ("saldo-1s", f"O saldo orçamentário da área {nome} no 1º semestre de 2026 foi de {brl(saldo1s)}.",
             [f"Qual o saldo orçamentário de {nome} no primeiro semestre de 2026?", f"A área {nome} ficou acima ou abaixo do orçamento no 1º semestre de 2026?"],
             f"saldo 1º semestre {nome}", f"O saldo da área {nome} no 1º semestre de 2026 foi de {brl(saldo1s)}, somando 2026T1 e 2026T2; saldo positivo significa gasto abaixo do orçado e negativo, acima.", f"| Orçado 1º semestre |"),
        ]
        for chave, fato, qs, k, a, ev in itens:
            out.append({
                "fato_id": f"financeiro-orcamento-{d['id']}-{chave}", "area": "financeiro", "fato": fato, "fonte_doc": rel,
                "destino": "rag", "sensibilidade": "gestores", "perguntas": qs, "chave": k, "resposta": a,
                "evidencia": ev,
            })
    return out


def fatos_catalogo():
    rel = "docs/comercial/portfolio-servicos.md"
    out = []
    for s in ler_csv("data/catalogo_servicos.csv"):
        preco = float(s["preco_unitario_brl"])
        ev = next(l for l in ler_doc(rel)[1].splitlines() if l.startswith(f"| {s['codigo']} |"))
        nome, cod = s["servico"], s["codigo"]
        out.append({
            "fato_id": f"comercial-catalogo-{cod.lower()}-preco", "area": "comercial",
            "fato": f"O preço de tabela do serviço {nome} ({cod}) é de {brl2(preco)} por {s['unidade_cobranca']}.",
            "fonte_doc": rel, "destino": "rag", "sensibilidade": "publico",
            "perguntas": [f"Qual o preço de tabela do serviço {nome}?", f"Quanto custa o serviço {cod} ({nome})?"],
            "chave": f"preço {cod}", "resposta": f"O serviço {nome} ({cod}) custa {brl2(preco)} por {s['unidade_cobranca']} na tabela vigente.",
            "evidencia": ev})
        out.append({
            "fato_id": f"comercial-catalogo-{cod.lower()}-disponibilidade", "area": "comercial",
            "fato": f"O serviço {nome} ({cod}) está disponível em: {s['disponibilidade']}. Observação: {s['observacao']}.",
            "fonte_doc": rel, "destino": "rag", "sensibilidade": "publico",
            "perguntas": [f"Em quais unidades está disponível o serviço {nome}?", f"O serviço {cod} é oferecido em Campinas e em Uberlândia?"],
            "chave": f"disponibilidade {cod}", "resposta": f"O serviço {nome} ({cod}) está disponível em: {s['disponibilidade']}. Observação: {s['observacao']}.",
            "evidencia": ev})
    return out


def fatos_diretorio(ficha, rng):
    func = ler_csv("data/funcionarios.csv")
    por_id = {f["id"]: f for f in func}
    rel = "data/funcionarios.csv"
    lideres = {d["diretor"] for d in ficha["departamentos"]}
    linha = lambda f: linha_diretorio(f, por_id)
    out = []
    for f in func:
        if f["nome"] in lideres:
            out.append({
                "fato_id": f"diretorio-ramal-{f['id']}", "area": "institucional",
                "fato": f"O ramal de {f['nome']} ({f['cargo']}) é {f['ramal']} e o e-mail é {f['email']}.",
                "fonte_doc": rel, "destino": "rag", "sensibilidade": "publico",
                "perguntas": [f"Qual o ramal de {f['nome']}?", f"Qual o e-mail e o ramal de {f['nome']}, {f['cargo']}?"],
                "chave": f"ramal {f['nome']}",
                "resposta": f"{f['nome']} é {f['cargo']} ({f['departamento']}). O ramal é {f['ramal']} e o e-mail é {f['email']}.",
                "evidencia": linha(f)})
    amostra = [f for f in func if f["nome"] not in lideres and f["gestor_id"]]
    for f in rng.sample(amostra, 34):
        g = por_id[f["gestor_id"]]
        out.append({
            "fato_id": f"diretorio-ramal-{f['id']}", "area": "institucional",
            "fato": f"O ramal de {f['nome']} ({f['cargo']}, {f['departamento']}) é {f['ramal']}.",
            "fonte_doc": rel, "destino": "rag", "sensibilidade": "publico",
            "perguntas": [f"Qual o ramal de {f['nome']}?", f"Preciso falar com {f['nome']}, qual é o ramal?"],
            "chave": f"ramal {f['nome']}",
            "resposta": f"O ramal de {f['nome']} ({f['cargo']}, {f['departamento']}, {f['unidade']}) é {f['ramal']}.",
            "evidencia": linha(f)})
        out.append({
            "fato_id": f"diretorio-gestor-{f['id']}", "area": "institucional",
            "fato": f"O gestor imediato de {f['nome']} é {g['nome']} ({g['cargo']}).",
            "fonte_doc": rel, "destino": "rag", "sensibilidade": "publico",
            "perguntas": [f"Quem é o gestor de {f['nome']}?", f"A quem {f['nome']} se reporta?"],
            "chave": f"gestor {f['nome']}",
            "resposta": f"O gestor imediato de {f['nome']} ({f['cargo']}) é {g['nome']}, {g['cargo']}.",
            "evidencia": linha(f)})
    return out


def _linha_tabela(rel, inicio):
    for l in ler_doc(rel)[1].splitlines():
        if l.startswith(inicio):
            return l
    raise AssertionError(f"linha não encontrada em {rel}: {inicio!r}")


def fatos_extra(ficha, ctx):
    """Fatos programáticos adicionais: quadro por área, DRE anual, calendário de fechamento e famílias de serviços."""
    out = []
    rel = "docs/institucional/organograma.md"
    for d in ficha["departamentos"]:
        h = ctx["hc"][d["nome"]]
        ev = _linha_tabela(rel, f"| {d['nome']} |")
        out.append({
            "fato_id": f"institucional-quadro-{d['id']}", "area": "institucional",
            "fato": f"{d['nome']} tem {h['total']} colaboradores ({h['Campinas/SP']} em Campinas e {h['Uberlândia/MG']} em Uberlândia) e é liderada por {d['diretor']}.",
            "fonte_doc": rel, "destino": "rag", "sensibilidade": "publico",
            "perguntas": [f"Quantas pessoas trabalham na área {d['nome']}?", f"Quantos colaboradores e quantas unidades tem a área {d['nome']}?"],
            "chave": f"headcount {d['nome']}",
            "resposta": f"A área {d['nome']} tem {h['total']} colaboradores: {h['Campinas/SP']} em Campinas e {h['Uberlândia/MG']} em Uberlândia. A liderança é de {d['diretor']} ({d['cargo_diretor']}).",
            "evidencia": ev})
    rel = "docs/financeiro/resumo-dre.md"
    rotulos = [("receita_bruta", "Receita bruta", "a receita bruta"), ("receita_liquida", "Receita líquida", "a receita líquida"),
               ("cmv", "CMV", "o CMV"), ("lucro_bruto", "Lucro bruto", "o lucro bruto"),
               ("despesas_operacionais", "Despesas operacionais", "as despesas operacionais"), ("ebitda", "EBITDA", "o EBITDA"),
               ("resultado_liquido", "Resultado líquido", "o resultado líquido")]
    for ano in ("2024", "2025"):
        for col, rot, art in rotulos:
            if col in ("receita_liquida", "ebitda", "resultado_liquido") and ano == "2025":
                continue  # já cobertos pelos fatos escritos à mão
            ev = next((l for l in ler_doc(rel)[1].splitlines() if l.startswith(f"| {rot} |") or l.startswith(f"| **{rot}** |")))
            v = brl(ctx["anual"][ano][col])
            verbo = "foram" if col == "despesas_operacionais" else "foi"
            out.append({
                "fato_id": f"financeiro-dre-{ano}-total-{col.replace('_', '-')}", "area": "financeiro",
                "fato": f"No total de {ano}, {art} {verbo} de {v}.", "fonte_doc": rel, "destino": "rag", "sensibilidade": "financeiro_restrito",
                "perguntas": [f"{'Quais foram' if verbo == 'foram' else 'Qual foi'} {art} em {ano}?",
                              f"Quanto {verbo} {art} da empresa somando todo o ano de {ano}?"],
                "chave": f"{rot.lower()} total {ano}",
                "resposta": f"No total de {ano}, {art} da Brisa Log {verbo} de {v}, segundo o resumo da DRE (documento de acesso restrito).",
                "evidencia": ev})
    rel = "docs/financeiro/calendario-fechamento.md"
    for m in ctx["fechamentos"]:
        ev = _linha_tabela(rel, f"| {m['mes'].capitalize()} |")
        d = lambda x: f"{x.day:02d}/{x.month:02d}/{x.year}"
        out.append({
            "fato_id": f"financeiro-fechamento-{m['mes']}", "area": "financeiro",
            "fato": f"O fechamento contábil de {m['mes']} de 2026 ocorre em {d(m['fechamento'])}, com corte de despesas em {d(m['corte'])}.",
            "fonte_doc": rel, "destino": "rag", "sensibilidade": "publico",
            "perguntas": [f"Quando é o fechamento contábil de {m['mes']} de 2026?", f"Qual o prazo para lançar despesas de {m['mes']} antes do fechamento?"],
            "chave": f"fechamento {m['mes']} 2026",
            "resposta": f"Para o mês de {m['mes']} de 2026, o corte de despesas é em {d(m['corte'])}, a conciliação em {d(m['conciliacao'])} e o fechamento em {d(m['fechamento'])}.",
            "evidencia": ev})
    rel = "docs/comercial/portfolio-servicos.md"
    for cat in dict.fromkeys(s["categoria"] for s in ctx["servicos"]):
        nomes = [s["servico"] for s in ctx["servicos"] if s["categoria"] == cat]
        out.append({
            "fato_id": f"comercial-familia-{slug(cat)}", "area": "comercial",
            "fato": f"A família {cat} reúne {len(nomes)} serviços: {'; '.join(nomes)}.", "fonte_doc": rel, "destino": "rag",
            "sensibilidade": "publico",
            "perguntas": [f"Quais serviços fazem parte da família {cat}?", f"Quantos serviços de {cat.lower()} a Brisa Log oferece?"],
            "chave": f"serviços de {cat.lower()}",
            "resposta": f"A família {cat} reúne {len(nomes)} serviços: {'; '.join(nomes)}.",
            "evidencia": f"## {cat}"})
    return out


def main():
    ficha = carregar_ficha()
    ctx = contexto()
    rng = random.Random(ficha["empresa"]["seed"] + 2)
    fatos = fatos_manuais(ficha, ctx) + fatos_financeiro() + fatos_orcamento(ficha) + fatos_catalogo() + fatos_diretorio(ficha, rng) + fatos_extra(ficha, ctx)
    ids = [f["fato_id"] for f in fatos]
    assert len(ids) == len(set(ids)), "fato_id duplicado"
    escrever_jsonl("fatos/fatos.jsonl", fatos)
    ft = sum(f["destino"] == "finetuning" for f in fatos)
    print(f"fatos/fatos.jsonl: {len(fatos)} fatos ({ft} finetuning, {len(fatos) - ft} rag)")


if __name__ == "__main__":
    main()
