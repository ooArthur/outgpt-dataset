"""Testes determinísticos do controle de acesso. Uso: python scripts/teste_acesso.py (sai com 1 se algo falhar)."""
import sys
from collections import Counter

from acesso import acesso_da_fonte, filtrar_trechos, fontes_permitidas, matriz, niveis_do_perfil, pode_ver
from common import RAIZ, ler_doc, ler_jsonl


def rodar():
    erros = []
    docs = sorted(p.relative_to(RAIZ).as_posix() for p in (RAIZ / "docs").glob("*/*.md"))
    niveis_docs = {ler_doc(d)[0]["acesso"] for d in docs}
    perfis = matriz()["perfis"]
    # 1) a matriz cobre todo nível presente nos documentos e não inventa níveis
    cobertos = {n for v in perfis.values() for n in v}
    for n in niveis_docs - cobertos:
        erros.append(f"nível de acesso {n!r} existe nos documentos mas nenhum perfil o enxerga")
    for p, v in perfis.items():
        for n in v:
            if n not in niveis_docs:
                erros.append(f"perfil {p!r} vê o nível {n!r}, que não existe em nenhum documento")
    if "publico" not in perfis.get("colaborador", []):
        erros.append("colaborador deve ver ao menos o nível publico")
    if set(perfis["diretoria"]) != niveis_docs:
        erros.append("diretoria deve enxergar todos os níveis existentes")
    # 2) CSVs: sensibilidade dos fatos concorda com a configurada
    fatos_csv = {}
    for f in ler_jsonl("fatos/fatos.jsonl"):
        if f["fonte_doc"].endswith(".csv"):
            fatos_csv.setdefault(f["fonte_doc"], set()).add(f["sensibilidade"])
    for rel, niv in fatos_csv.items():
        cfg = matriz()["fontes_csv"].get(rel)
        if len(niv) != 1 or (cfg and cfg not in niv):
            erros.append(f"{rel}: sensibilidade dos fatos {sorted(niv)} diverge de fontes_csv ({cfg})")
    # 3) filtro: o colaborador não recebe documentos restritos; a diretoria recebe tudo
    todos = [(d, "x") for d in docs]
    vistos = {d for d, _ in filtrar_trechos("colaborador", todos)}
    for d in docs:
        if (acesso_da_fonte(d) == "publico") != (d in vistos):
            erros.append(f"filtro de colaborador incorreto para {d}")
    if {d for d, _ in filtrar_trechos("diretoria", todos)} != set(docs):
        erros.append("diretoria deveria ver todos os documentos")
    if set(fontes_permitidas("colaborador")) & {d for d in docs if acesso_da_fonte(d) != "publico"}:
        erros.append("fontes_permitidas(colaborador) inclui documento restrito")
    # 4) itens de avaliação de acesso
    itens = ler_jsonl("avaliacao/perguntas_acesso.jsonl")
    cont = Counter(i["comportamento"] for i in itens)
    if len(itens) != 20 or cont["negar"] != 10 or cont["responder"] != 10:
        erros.append(f"perguntas_acesso.jsonl deve ter 20 itens (10 negar e 10 responder); tem {len(itens)} {dict(cont)}")
    restritos = {d for d in docs if acesso_da_fonte(d) != "publico"}
    usados = {f for i in itens for f in i["fonte_doc"]}
    for d in restritos - usados:
        erros.append(f"documento restrito sem pergunta de acesso: {d}")
    csv_restritos = [i for i in itens if any(f.endswith(".csv") and acesso_da_fonte(f) != "publico" for f in i["fonte_doc"])]
    if len(csv_restritos) < 3:
        erros.append(f"menos de 3 perguntas de acesso sobre CSVs restritos ({len(csv_restritos)})")
    publicas = [i for i in itens if i["perfil"] == "colaborador" and i["comportamento"] == "responder"
                and all(acesso_da_fonte(f) == "publico" for f in i["fonte_doc"])]
    if len(publicas) < 3:
        erros.append(f"menos de 3 perguntas públicas feitas por colaborador ({len(publicas)})")
    espelhos = Counter(i["pergunta"] for i in itens)
    if sum(1 for q, n in espelhos.items() if n == 2) < 5:
        erros.append("poucos pares espelho (mesma pergunta para perfis diferentes)")
    for n, i in enumerate(itens, 1):
        try:
            niveis_do_perfil(i["perfil"])
        except ValueError as e:
            erros.append(f"item {n}: {e}")
            continue
        for f in i["fonte_doc"]:
            if not (RAIZ / f).exists():
                erros.append(f"item {n}: fonte inexistente {f}")
                continue
            ok = pode_ver(i["perfil"], f)
            if i["comportamento"] == "negar" and ok:
                erros.append(f"item {n}: perfil {i['perfil']} PODE ver {f}, mas o item espera negar")
            if i["comportamento"] == "responder" and not ok:
                erros.append(f"item {n}: perfil {i['perfil']} NÃO pode ver {f}, mas o item espera responder")
        if i["comportamento"] == "negar" and "@brisalog.example" not in i["resposta_esperada"]:
            erros.append(f"item {n}: resposta de negação sem e-mail da área")
    return erros, {"itens": len(itens), **dict(cont), "csv_restritos": len(csv_restritos), "publicas": len(publicas),
                   "pares_espelho": sum(1 for n in espelhos.values() if n == 2)}


if __name__ == "__main__":
    e, s = rodar()
    for x in e:
        print("ERRO:", x)
    print(f"teste_acesso: {len(e)} erro(s) | {s}")
    sys.exit(1 if e else 0)
