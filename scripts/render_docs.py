"""Renderiza templates/*/*.md.j2 em docs/*/*.md com valores da ficha-mestra e dos CSVs."""
import datetime as dt
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from common import (RAIZ, RODAPE, brl, brl2, carregar_ficha, data_br, dia_semana, dia_util_n, ler_csv, milhoes,
                    num, pct, MESES)


def contexto():
    f = carregar_ficha()
    fin = [{k: (v if k == "trimestre" else int(v)) for k, v in l.items()}
           for l in ler_csv("data/financeiro_trimestral.csv")]
    anual = {}
    for l in fin:
        ano = l["trimestre"][:4]
        a = anual.setdefault(ano, {k: 0 for k in l if k != "trimestre"})
        for k in a:
            a[k] += l[k]
    orc = ler_csv("data/orcamento_departamentos_2026.csv")
    for l in orc:
        for k in ("orcado", "realizado", "saldo"):
            l[k] = int(l[k]) if l[k] != "" else None
    por_dep = {}
    for d in f["departamentos"]:
        linhas = [l for l in orc if l["departamento"] == d["nome"]]
        real = [l for l in linhas if l["realizado"] is not None]
        por_dep[d["id"]] = {
            "nome": d["nome"], "anual": sum(l["orcado"] for l in linhas), "linhas": linhas,
            "orcado_1s": sum(l["orcado"] for l in real), "realizado_1s": sum(l["realizado"] for l in real),
            "saldo_1s": sum(l["saldo"] for l in real),
        }
    func = ler_csv("data/funcionarios.csv")
    hc = {}
    for l in func:
        hc.setdefault(l["departamento"], {"total": 0, "Campinas/SP": 0, "Uberlândia/MG": 0})
        hc[l["departamento"]]["total"] += 1
        hc[l["departamento"]][l["unidade"]] += 1
    fech = []
    fer = f["financeiro"]["fechamento"]
    for m in range(1, 13):
        ref = dt.date(2026, m, 1)
        nm, na = (m % 12) + 1, 2026 + (m // 12)  # fechamento do mês m ocorre no mês seguinte
        fech.append({
            "mes": MESES[m - 1], "corte": dia_util_n(na, nm, fer["dia_util_corte_despesas"], fer["feriados_2026"] if na == 2026 else []),
            "conciliacao": dia_util_n(na, nm, fer["dia_util_conciliacao"], fer["feriados_2026"] if na == 2026 else []),
            "fechamento": dia_util_n(na, nm, fer["dia_util_fechamento"], fer["feriados_2026"] if na == 2026 else []),
        })
    adm = sum(v["total"] for k, v in hc.items() if k != "Operações e Logística")
    return {
        "f": f, "fin": fin, "anual": anual, "orc": orc, "orc_dep": por_dep, "hc": hc, "hc_adm": adm,
        "fechamentos": fech, "servicos": f["catalogo_servicos"],
        "dep": {d["id"]: d for d in f["departamentos"]},
        "iso_br": lambda s: data_br(dt.date.fromisoformat(s)),
        "brl": brl, "brl2": brl2, "num": num, "pct": pct, "milhoes": milhoes, "data_br": data_br, "dia_semana": dia_semana,
        "email": lambda caixa: f"{caixa}@{f['empresa']['dominio_email']}",
        "total_orc_2026": sum(d["orcamento_2026"] for d in f["departamentos"]),
    }


def renderizar_todos(somente=None):
    ctx = contexto()
    env = Environment(loader=FileSystemLoader(str(RAIZ / "templates")), undefined=StrictUndefined,
                      trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
    gerados = []
    for tpl in sorted((RAIZ / "templates").glob("*/*.md.j2")):
        area, nome = tpl.parent.name, tpl.name[:-len(".md.j2")]
        if somente and f"{area}/{nome}" not in somente:
            continue
        texto = env.get_template(f"{area}/{tpl.name}").render(**ctx).rstrip() + "\n\n" + RODAPE + "\n"
        destino = RAIZ / "docs" / area / f"{nome}.md"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto, encoding="utf-8")
        gerados.append(destino)
    return gerados


if __name__ == "__main__":
    g = renderizar_todos(set(sys.argv[1:]) or None)
    print(f"docs/: {len(g)} documentos renderizados")
