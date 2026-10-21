"""Valida toda a base e gera validacao/relatorio.md. Sai com código 1 se houver erro.

Uso: python validacao/validar.py [--readme]   (--readme atualiza a tabela de estatísticas do README)
"""
import csv
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from common import (AREAS_DOC, RAIZ, RODAPE, SYSTEM_PROMPT, carregar_ficha, ler_csv, ler_doc, normaliza)  # noqa: E402

CAMPOS_FM = ["titulo", "area", "versao", "vigencia", "acesso", "responsavel"]
ACESSOS = {"publico", "gestores", "rh_restrito", "financeiro_restrito"}
CATEGORIAS = {"Acesso e Senhas", "E-mail e Colaboração", "Rede e VPN", "Hardware", "Software e Licenças", "Sistemas Internos", "Impressão", "Segurança"}
FILAS = {"N1", "N2", "Infraestrutura", "Sistemas", "Segurança"}
TIPOS_QA = {"direta", "com_contexto", "sem_resposta", "multi_turno", "fora_de_escopo"}
TIPOS_AVAL = {"simples", "numerica", "multi-documento", "versao_antiga_vs_nova", "sem_resposta", "fora_de_escopo"}
SEGREDOS = re.compile(r"(ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA |EC )?PRIVATE KEY)")

erros, avisos, stats = [], [], {}


def erro(msg):
    erros.append(msg)


def jsonl(caminho):
    linhas = []
    for i, l in enumerate((RAIZ / caminho).read_text(encoding="utf-8").splitlines(), 1):
        if not l.strip():
            continue
        try:
            linhas.append(json.loads(l))
        except json.JSONDecodeError as e:
            erro(f"{caminho}:{i} JSON inválido ({e})")
    return linhas


def pergunta_de(texto):
    return texto.split("PERGUNTA:")[-1].strip()


# ----------------------------------------------------------------------------- documentos
def checa_docs(ficha):
    docs = sorted((RAIZ / "docs").glob("*/*.md"))
    por_area, palavras = Counter(), []
    for p in docs:
        rel = p.relative_to(RAIZ).as_posix()
        txt = p.read_text(encoding="utf-8")
        if not txt.startswith("---\n"):
            erro(f"{rel}: sem front matter")
            continue
        try:
            meta, corpo = ler_doc(rel)
        except Exception as e:  # noqa: BLE001
            erro(f"{rel}: front matter inválido ({e})")
            continue
        for c in CAMPOS_FM:
            if not meta.get(c):
                erro(f"{rel}: front matter sem '{c}'")
        if meta.get("acesso") not in ACESSOS:
            erro(f"{rel}: acesso inválido {meta.get('acesso')!r}")
        if meta.get("area") != p.parent.name:
            erro(f"{rel}: area '{meta.get('area')}' difere da pasta")
        if "{{" in txt or "}}" in txt or "{%" in txt:
            erro(f"{rel}: marcação Jinja sobrando")
        if txt.rstrip().splitlines()[-1] != RODAPE:
            erro(f"{rel}: não termina com a linha de aviso fictício")
        n = sum(1 for w in corpo.split() if re.search(r"\w", w))
        palavras.append(n)
        if not 300 <= n <= 900:
            erro(f"{rel}: {n} palavras (esperado 300 a 900)")
        for ref in (meta.get("substitui"), meta.get("substituido_por")):
            if ref and not (RAIZ / "docs" / f"{ref}.md").exists():
                erro(f"{rel}: referência de versão inexistente {ref}")
        por_area[p.parent.name] += 1
    if not 30 <= len(docs) <= 60:
        erro(f"quantidade de documentos fora de 30-60: {len(docs)}")
    pares = sum(1 for p in docs if "-v2025" in p.name)
    if pares < 3:
        erro(f"menos de 3 pares de versão antiga e nova ({pares})")
    stats["docs"] = {"total": len(docs), "por_area": dict(por_area), "palavras_min": min(palavras), "palavras_max": max(palavras),
                     "palavras_media": round(sum(palavras) / len(palavras)), "pares_versao": pares}


# ----------------------------------------------------------------------------- CSVs
def checa_csvs(ficha):
    func = ler_csv("data/funcionarios.csv")
    ids = [f["id"] for f in func]
    if len(set(ids)) != len(ids):
        erro("funcionarios.csv: ids duplicados")
    if set(func[0].keys()) != {"id", "nome", "cargo", "departamento", "gestor_id", "unidade", "data_admissao", "ramal", "email"}:
        erro(f"funcionarios.csv: colunas inesperadas {list(func[0].keys())}")
    sem_gestor = [f["nome"] for f in func if not f["gestor_id"]]
    if sem_gestor != ["Helena Monteiro Duarte"]:
        erro(f"funcionarios.csv: apenas a CEO pode ficar sem gestor_id; encontrados {sem_gestor}")
    for f in func:
        if f["gestor_id"] and f["gestor_id"] not in ids:
            erro(f"funcionarios.csv: gestor_id inexistente {f['gestor_id']} (id {f['id']})")
        if f["gestor_id"] == f["id"]:
            erro(f"funcionarios.csv: id {f['id']} é gestor de si mesmo")
        if not f["email"].endswith("@" + ficha["empresa"]["dominio_email"]):
            erro(f"funcionarios.csv: e-mail fora do domínio fictício ({f['email']})")
        dt.date.fromisoformat(f["data_admissao"])
    if len({f["email"] for f in func}) != len(func):
        erro("funcionarios.csv: e-mails duplicados")
    if len(func) != ficha["empresa"]["colaboradores"]:
        erro(f"funcionarios.csv: {len(func)} linhas, ficha diz {ficha['empresa']['colaboradores']}")
    por_dep = Counter(f["departamento"] for f in func)
    for d in ficha["departamentos"]:
        esperado = sum(sum(c["qtd"].values()) for c in ficha["quadro"][d["id"]])
        if por_dep[d["nome"]] != esperado:
            erro(f"funcionarios.csv: {d['nome']} tem {por_dep[d['nome']]} linhas, ficha diz {esperado}")

    fin = ler_csv("data/financeiro_trimestral.csv")
    esperados = [f"{a}T{t}" for a in (2024, 2025, 2026) for t in range(1, 5)][:10]
    if [r["trimestre"] for r in fin] != esperados:
        erro("financeiro_trimestral.csv: trimestres devem ir de 2024T1 a 2026T2")
    for r in fin:
        v = {k: int(x) for k, x in r.items() if k != "trimestre"}
        t = r["trimestre"]
        checks = [
            (v["receita_liquida"], v["receita_bruta"] - v["deducoes"], "receita líquida = bruta - deduções"),
            (v["lucro_bruto"], v["receita_liquida"] - v["cmv"], "lucro bruto = líquida - CMV"),
            (v["ebitda"], v["lucro_bruto"] - v["despesas_operacionais"], "EBITDA = lucro bruto - despesas operacionais"),
            (v["resultado_liquido"], v["ebitda"] - v["depreciacao_amortizacao"] + v["resultado_financeiro"] - v["ir_csll"],
             "resultado líquido = EBITDA - D&A + resultado financeiro - IR/CSLL"),
        ]
        for obtido, esperado, nome in checks:
            if obtido != esperado:
                erro(f"financeiro_trimestral.csv {t}: {nome} não fecha ({obtido} != {esperado})")
    liq25 = sum(int(r["receita_liquida"]) for r in fin if r["trimestre"].startswith("2025"))
    if liq25 != ficha["empresa"]["faturamento_liquido_2025"]:
        erro(f"receita líquida 2025 ({liq25}) difere da ficha ({ficha['empresa']['faturamento_liquido_2025']})")

    orc = ler_csv("data/orcamento_departamentos_2026.csv")
    for d in ficha["departamentos"]:
        linhas = [r for r in orc if r["departamento"] == d["nome"]]
        if sum(int(r["orcado"]) for r in linhas) != d["orcamento_2026"]:
            erro(f"orcamento: soma anual de {d['nome']} difere da ficha")
        for r in linhas:
            if r["status"] == "realizado" and int(r["saldo"]) != int(r["orcado"]) - int(r["realizado"]):
                erro(f"orcamento: saldo não fecha em {d['nome']} {r['trimestre']}")
    cat = ler_csv("data/catalogo_servicos.csv")
    if len({c["codigo"] for c in cat}) != len(cat) or len(cat) != len(ficha["catalogo_servicos"]):
        erro("catalogo_servicos.csv: códigos duplicados ou quantidade diferente da ficha")
    for c in cat:
        if float(c["preco_unitario_brl"]) <= 0:
            erro(f"catalogo_servicos.csv: preço inválido em {c['codigo']}")
    stats["csv"] = {"funcionarios": len(func), "financeiro_trimestral": len(fin), "orcamento_departamentos_2026": len(orc), "catalogo_servicos": len(cat)}


# ----------------------------------------------------------------------------- fatos / QA / avaliação
def checa_fatos():
    fatos = jsonl("fatos/fatos.jsonl")
    ids = [f.get("fato_id") for f in fatos]
    if len(ids) != len(set(ids)):
        erro("fatos.jsonl: fato_id duplicado")
    for f in fatos:
        for c in ("fato_id", "area", "fato", "fonte_doc", "destino", "sensibilidade"):
            if not f.get(c):
                erro(f"fatos.jsonl {f.get('fato_id')}: campo '{c}' ausente")
        if f.get("destino") not in ("finetuning", "rag"):
            erro(f"fatos.jsonl {f.get('fato_id')}: destino inválido")
        if f.get("sensibilidade") not in ACESSOS:
            erro(f"fatos.jsonl {f.get('fato_id')}: sensibilidade inválida")
        if not (RAIZ / f.get("fonte_doc", "?")).exists():
            erro(f"fatos.jsonl {f.get('fato_id')}: fonte_doc inexistente {f.get('fonte_doc')}")
    if len(fatos) < 350:
        erro(f"fatos.jsonl: {len(fatos)} fatos (mínimo 350)")
    stats["fatos"] = {"total": len(fatos), "destino": dict(Counter(f["destino"] for f in fatos)),
                      "area": dict(Counter(f["area"] for f in fatos)), "sensibilidade": dict(Counter(f["sensibilidade"] for f in fatos))}
    return {f["fato_id"]: f for f in fatos}


def checa_qa(fatos):
    split = {"treino": jsonl("qa/qa_treino.jsonl"), "teste": jsonl("qa/qa_teste.jsonl")}
    perguntas, ids_split = {}, {"treino": set(), "teste": set()}
    por_tipo = {sp: Counter() for sp in split}
    for sp, regs in split.items():
        for i, r in enumerate(regs, 1):
            loc = f"qa_{sp}.jsonl:{i}"
            m, meta = r.get("messages", []), r.get("meta", {})
            papeis = [x.get("role") for x in m]
            if not papeis or papeis[0] != "system" or m[0]["content"] != SYSTEM_PROMPT:
                erro(f"{loc}: system prompt ausente ou diferente do padrão")
            esperado = ["system"] + ["user", "assistant"] * ((len(m) - 1) // 2)
            if papeis != esperado or len(m) < 3:
                erro(f"{loc}: sequência de papéis inválida {papeis}")
            if any(not x.get("content", "").strip() for x in m):
                erro(f"{loc}: mensagem vazia")
            for c in ("fato_id", "tipo", "area", "fonte_doc"):
                if c not in meta:
                    erro(f"{loc}: meta sem '{c}'")
            tipo = meta.get("tipo")
            if tipo not in TIPOS_QA:
                erro(f"{loc}: tipo inválido {tipo}")
            por_tipo[sp][tipo] += 1
            if meta.get("fonte_doc") and not (RAIZ / meta["fonte_doc"]).exists():
                erro(f"{loc}: fonte_doc inexistente {meta['fonte_doc']}")
            for fid in meta.get("fato_ids", [meta.get("fato_id")]):
                ids_split[sp].add(fid)
            for x in m:
                if x["role"] == "user":
                    q = normaliza(pergunta_de(x["content"]))
                    if q in perguntas:
                        erro(f"{loc}: pergunta duplicada (também em {perguntas[q]}): {pergunta_de(x['content'])[:70]!r}")
                    perguntas[q] = loc
            u = m[1]["content"] if len(m) > 1 else ""
            if tipo == "com_contexto" and not (u.startswith("CONTEXTO:\n") and "\n\nPERGUNTA: " in u):
                erro(f"{loc}: com_contexto fora do formato CONTEXTO/PERGUNTA")
            if tipo == "direta" and "CONTEXTO:" in u:
                erro(f"{loc}: direta com contexto")
            if tipo == "direta" and meta.get("fato_id") in fatos and fatos[meta["fato_id"]]["destino"] != "finetuning":
                erro(f"{loc}: fato de destino rag em pergunta direta ({meta['fato_id']})")
            if tipo == "sem_resposta" and not m[-1]["content"].startswith("Não encontrei essa informação nos documentos da empresa. Sugiro falar com"):
                erro(f"{loc}: resposta de sem_resposta fora do padrão")
            if tipo == "multi_turno" and not 5 <= len(m) <= 7:
                erro(f"{loc}: multi_turno deve ter 2 a 3 turnos")
            if tipo in ("direta", "com_contexto", "multi_turno") and meta.get("fato_id") not in fatos:
                erro(f"{loc}: fato_id desconhecido {meta.get('fato_id')}")
    vazamento = ids_split["treino"] & ids_split["teste"]
    if vazamento:
        erro(f"fato_id presente no treino e no teste: {sorted(vazamento)[:5]} ({len(vazamento)})")
    total = sum(sum(c.values()) for c in por_tipo.values())
    if total < 1500:
        erro(f"qa: {total} pares (mínimo 1500)")
    tot_tipo = sum(por_tipo.values(), Counter())
    for tipo, alvo in (("sem_resposta", 0.15), ("multi_turno", 0.05), ("fora_de_escopo", 0.03)):
        pc = tot_tipo[tipo] / total
        if abs(pc - alvo) > alvo * 0.35:
            avisos.append(f"proporção de {tipo} = {pc:.1%} (alvo ≈ {alvo:.0%})")
    por_fato = Counter(r["meta"]["fato_id"] for r in split["treino"] + split["teste"] if r["meta"]["tipo"] in ("direta", "com_contexto"))
    abaixo = sum(1 for n in por_fato.values() if n < 3)
    if abaixo:
        avisos.append(f"{abaixo} fatos com menos de 3 formulações (de {len(por_fato)})")
    cobertos = set(por_fato)
    sem_qa = [fid for fid in fatos if fid not in cobertos]
    if sem_qa:
        erro(f"{len(sem_qa)} fatos sem nenhuma pergunta em direta/com_contexto (ex.: {sem_qa[:3]})")
    stats["qa"] = {"treino": len(split["treino"]), "teste": len(split["teste"]), "total": total,
                   "tipo_treino": dict(por_tipo["treino"]), "tipo_teste": dict(por_tipo["teste"]),
                   "fatos_treino": len(ids_split["treino"]), "fatos_teste": len(ids_split["teste"]),
                   "formulacoes_por_fato": round(sum(por_fato.values()) / max(len(por_fato), 1), 2)}
    return perguntas


def checa_avaliacao(perguntas_qa):
    av = jsonl("avaliacao/perguntas_avaliacao.jsonl")
    if len(av) != 100:
        erro(f"avaliacao: {len(av)} perguntas (esperado 100)")
    vistas = set()
    for i, r in enumerate(av, 1):
        for c in ("pergunta", "resposta_esperada", "fonte_doc", "tipo"):
            if c not in r:
                erro(f"avaliacao:{i}: campo '{c}' ausente")
        if r.get("tipo") not in TIPOS_AVAL:
            erro(f"avaliacao:{i}: tipo inválido {r.get('tipo')}")
        q = normaliza(r.get("pergunta", ""))
        if q in perguntas_qa:
            erro(f"avaliacao:{i}: pergunta repetida do treino/teste ({perguntas_qa[q]})")
        if q in vistas:
            erro(f"avaliacao:{i}: pergunta duplicada na própria avaliação")
        vistas.add(q)
        fontes = r.get("fonte_doc") or []
        for d in fontes:
            if not (RAIZ / d).exists():
                erro(f"avaliacao:{i}: fonte_doc inexistente {d}")
        if r.get("tipo") in ("simples", "numerica", "multi-documento", "versao_antiga_vs_nova") and not fontes:
            erro(f"avaliacao:{i}: pergunta respondível sem fonte_doc")
    stats["avaliacao"] = {"total": len(av), "tipo": dict(Counter(r["tipo"] for r in av))}


def checa_tickets(ficha):
    t = ler_csv("tickets/tickets_ti.csv")
    if len(t) != 500:
        erro(f"tickets: {len(t)} linhas (esperado 500)")
    if len({r["id"] for r in t}) != len(t):
        erro("tickets: ids duplicados")
    for r in t:
        if r["categoria"] not in CATEGORIAS:
            erro(f"tickets {r['id']}: categoria inválida")
        if r["fila"] not in FILAS:
            erro(f"tickets {r['id']}: fila inválida")
        if r["prioridade"] not in ("P1", "P2", "P3", "P4"):
            erro(f"tickets {r['id']}: prioridade inválida")
        if r["tipo"] not in ("incidente", "requisição"):
            erro(f"tickets {r['id']}: tipo inválido")
        if r["sentimento"] not in ("neutro", "frustrado", "urgente", "positivo"):
            erro(f"tickets {r['id']}: sentimento inválido")
        if r["prioridade"] in ("P1", "P2") and r["tipo"] != "incidente":
            erro(f"tickets {r['id']}: {r['prioridade']} deve ser incidente (SLA crítico)")
        if r["prioridade"] == "P1" and r["sentimento"] == "positivo":
            erro(f"tickets {r['id']}: P1 com sentimento positivo é incoerente")
        if not r["descricao"].strip() or not r["assunto"].strip():
            erro(f"tickets {r['id']}: texto vazio")
        dt.date.fromisoformat(r["data"])
    stats["tickets"] = {"total": len(t), "categoria": dict(Counter(r["categoria"] for r in t)),
                        "prioridade": dict(sorted(Counter(r["prioridade"] for r in t).items())),
                        "sentimento": dict(Counter(r["sentimento"] for r in t)), "fila": dict(Counter(r["fila"] for r in t)),
                        "tipo": dict(Counter(r["tipo"] for r in t))}


def checa_repositorio():
    grandes = [p for p in RAIZ.rglob("*") if p.is_file() and ".git" not in p.parts and p.stat().st_size > 5 * 1024 * 1024]
    for p in grandes:
        erro(f"arquivo acima de 5 MB: {p.relative_to(RAIZ)}")
    for p in RAIZ.rglob("*"):
        if p.is_file() and ".git" not in p.parts and p.suffix in {".md", ".py", ".yaml", ".j2", ".csv", ".jsonl", ".txt", ".fatos"}:
            if SEGREDOS.search(p.read_text(encoding="utf-8", errors="ignore")):
                erro(f"possível segredo em {p.relative_to(RAIZ)}")
    stats["arquivos"] = {p.relative_to(RAIZ).as_posix(): round(p.stat().st_size / 1024, 1) for p in
                         sorted(RAIZ.glob("*/*.jsonl")) + sorted(RAIZ.glob("*/*.csv"))}


# ----------------------------------------------------------------------------- relatório
def tabela(d, c1="Item", c2="Qtd"):
    return f"| {c1} | {c2} |\n|---|---:|\n" + "\n".join(f"| {k} | {v} |" for k, v in d.items()) + "\n"


def relatorio():
    s = stats
    out = ["# Relatório de validação\n", f"Gerado por `validacao/validar.py`. **Status: {'✅ APROVADO' if not erros else '❌ REPROVADO'}** — {len(erros)} erro(s), {len(avisos)} aviso(s).\n"]
    if erros:
        out += ["## Erros\n"] + [f"- {e}" for e in erros[:200]] + [""]
    if avisos:
        out += ["## Avisos\n"] + [f"- {a}" for a in avisos] + [""]
    out += ["## Verificações\n", "- Documentos: front matter completo, sem marcação `{{ }}`, 300 a 900 palavras, rodapé fictício, pares de versão.",
            "- Financeiro: aritmética de todos os trimestres e receita líquida de 2025 igual à ficha.",
            "- Funcionários: todo `gestor_id` existe; e-mails no domínio fictício; headcount igual ao da ficha.",
            "- JSONL válidos; sem perguntas duplicadas; nenhum `fato_id` no treino e no teste; todo `fonte_doc` existe.",
            "- Perguntas de fatos `rag` aparecem só como `com_contexto`; avaliação sem repetir treino/teste; tickets coerentes com o SLA; sem arquivos > 5 MB nem segredos.\n"]
    out += ["## Contagens por arquivo\n", tabela({k: f"{v} KB" for k, v in s["arquivos"].items()}, "Arquivo", "Tamanho")]
    out += [f"\n- `docs/`: **{s['docs']['total']}** documentos ({s['docs']['palavras_min']}–{s['docs']['palavras_max']} palavras; média {s['docs']['palavras_media']}).\n"]
    out += ["### Documentos por área\n", tabela(s["docs"]["por_area"], "Área", "Documentos")]
    out += ["\n### CSVs (linhas)\n", tabela(s["csv"], "Arquivo", "Linhas")]
    out += ["\n### Fatos\n", f"Total: **{s['fatos']['total']}**\n\n", tabela(s["fatos"]["destino"], "Destino", "Fatos"), "\n",
            tabela(s["fatos"]["area"], "Área", "Fatos"), "\n", tabela(s["fatos"]["sensibilidade"], "Sensibilidade", "Fatos")]
    q = s["qa"]
    out += ["\n### Perguntas e respostas\n", f"Total: **{q['total']}** (treino {q['treino']}, teste {q['teste']}); fatos distintos: treino {q['fatos_treino']}, teste {q['fatos_teste']}; "
            f"formulações por fato (direta/com_contexto): {q['formulacoes_por_fato']}.\n\n",
            "| Tipo | Treino | Teste | Total |\n|---|---:|---:|---:|\n"]
    for tp in sorted(TIPOS_QA):
        a, b = q["tipo_treino"].get(tp, 0), q["tipo_teste"].get(tp, 0)
        out.append(f"| {tp} | {a} | {b} | {a + b} |\n")
    out += ["\n### Avaliação\n", tabela(s["avaliacao"]["tipo"], "Tipo", "Perguntas")]
    tk = s["tickets"]
    out += ["\n### Tickets de TI\n", tabela(tk["categoria"], "Categoria", "Tickets"), "\n", tabela(tk["prioridade"], "Prioridade", "Tickets"), "\n",
            tabela(tk["sentimento"], "Sentimento", "Tickets"), "\n", tabela(tk["fila"], "Fila", "Tickets"), "\n", tabela(tk["tipo"], "Tipo", "Tickets")]
    (RAIZ / "validacao" / "relatorio.md").write_text("".join(x if x.endswith("\n") or x == "" else x for x in out), encoding="utf-8")


def atualizar_readme():
    s = stats
    q = s["qa"]
    linhas = [
        "| Item | Quantidade |", "|---|---:|",
        f"| Documentos Markdown (`docs/`) | {s['docs']['total']} ({s['docs']['pares_versao']} pares de versão antiga e nova) |",
        f"| Funcionários (`data/funcionarios.csv`) | {s['csv']['funcionarios']} |",
        f"| Trimestres financeiros (2024T1–2026T2) | {s['csv']['financeiro_trimestral']} |",
        f"| Linhas de orçamento 2026 | {s['csv']['orcamento_departamentos_2026']} |",
        f"| Serviços no catálogo | {s['csv']['catalogo_servicos']} |",
        f"| Fatos atômicos (`fatos/fatos.jsonl`) | {s['fatos']['total']} ({s['fatos']['destino'].get('finetuning', 0)} finetuning, {s['fatos']['destino'].get('rag', 0)} rag) |",
        f"| Pares de QA (treino + teste) | {q['total']} ({q['treino']} + {q['teste']}) |",
    ]
    for tp in sorted(TIPOS_QA):
        linhas.append(f"| &nbsp;&nbsp;↳ `{tp}` | {q['tipo_treino'].get(tp, 0) + q['tipo_teste'].get(tp, 0)} |")
    linhas += [f"| Perguntas de avaliação | {s['avaliacao']['total']} |", f"| Tickets de TI | {s['tickets']['total']} |"]
    novo = "<!-- STATS:START -->\n" + "\n".join(linhas) + "\n<!-- STATS:END -->"
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    readme = re.sub(r"<!-- STATS:START -->.*?<!-- STATS:END -->", lambda _m: novo, readme, flags=re.S)
    (RAIZ / "README.md").write_text(readme, encoding="utf-8")


def main():
    ficha = carregar_ficha()
    checa_docs(ficha)
    checa_csvs(ficha)
    fatos = checa_fatos()
    perguntas = checa_qa(fatos)
    checa_avaliacao(perguntas)
    checa_tickets(ficha)
    checa_repositorio()
    relatorio()
    if "--readme" in sys.argv:
        atualizar_readme()
    print(f"validação: {len(erros)} erro(s), {len(avisos)} aviso(s) — ver validacao/relatorio.md")
    for e in erros[:30]:
        print("  ERRO:", e)
    for a in avisos:
        print("  aviso:", a)
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
