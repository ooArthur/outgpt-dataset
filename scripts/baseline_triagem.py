"""Baseline de triagem de tickets de TI: TF-IDF (palavras + caracteres) + regressão logística.

Uso: python scripts/baseline_triagem.py      (requer scikit-learn: pip install -r requirements-opcional.txt)
Grava validacao/baseline_tickets.md. Não faz parte do build_all.py.
"""
import sys

try:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
    from sklearn.model_selection import StratifiedKFold, train_test_split
    from sklearn.pipeline import FeatureUnion, make_pipeline
except ImportError:
    sys.exit("Este script precisa de scikit-learn. Instale com: pip install -r requirements-opcional.txt")

from common import RAIZ, carregar_ficha, ler_csv

ALVOS = ["categoria", "fila", "prioridade", "sentimento", "tipo"]


def modelo(seed):
    vet = FeatureUnion([
        ("palavras", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, lowercase=True)),
        ("caracteres", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=2, lowercase=True)),
    ])
    return make_pipeline(vet, LogisticRegression(max_iter=2000, C=10.0, random_state=seed))


def metricas(y, p):
    return round(100 * accuracy_score(y, p), 1), round(100 * f1_score(y, p, average="macro", zero_division=0), 1)


def main():
    seed = carregar_ficha()["empresa"]["seed"]
    t = ler_csv("tickets/tickets_ti.csv")
    textos = np.array([f"{r['assunto']} . {r['descricao']}" for r in t])
    dif = np.array([r["dificuldade"] for r in t])
    cat = np.array([r["categoria"] for r in t])
    idx = np.arange(len(t))
    tr, te = train_test_split(idx, test_size=0.2, random_state=seed, stratify=cat)
    out = ["# Baseline de triagem de tickets de TI\n",
           "TF-IDF (palavras 1-2 gramas + caracteres 2-5) + regressão logística, `scripts/baseline_triagem.py`. "
           f"Divisão 80/20 estratificada por categoria (seed {seed}): {len(tr)} treino, {len(te)} teste "
           f"({int((dif[te] == 'dificil').sum())} difíceis e {int((dif[te] == 'facil').sum())} fáceis no teste).\n",
           "## Divisão 80/20: acurácia e F1 macro (%)\n",
           "| Alvo | Acurácia (todos) | F1 macro (todos) | Acurácia fácil | F1 fácil | Acurácia difícil | F1 difícil |", "|---|---:|---:|---:|---:|---:|---:|"]
    pred_cat = None
    for alvo in ALVOS:
        y = np.array([r[alvo] for r in t])
        m = modelo(seed).fit(textos[tr], y[tr])
        p = m.predict(textos[te])
        if alvo == "categoria":
            pred_cat = p
        lin = [metricas(y[te], p)]
        for nivel in ("facil", "dificil"):
            sel = dif[te] == nivel
            lin.append(metricas(y[te][sel], p[sel]))
        out.append(f"| {alvo} | {lin[0][0]} | {lin[0][1]} | {lin[1][0]} | {lin[1][1]} | {lin[2][0]} | {lin[2][1]} |")

    out += ["\n## Validação cruzada (5 dobras estratificadas por categoria, predições fora da dobra)\n",
            "Com só ~100 tickets de teste, a diferença fácil x difícil é ruidosa; a validação cruzada usa os 500 tickets.\n",
            "| Alvo | Acurácia fácil | F1 fácil | Acurácia difícil | F1 difícil |", "|---|---:|---:|---:|---:|"]
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    amb = np.array([bool(r["categoria_secundaria"]) for r in t])
    extra = []
    for alvo in ALVOS:
        y = np.array([r[alvo] for r in t])
        oof = np.empty(len(t), dtype=object)
        for a, b in cv.split(textos, cat):
            oof[b] = modelo(seed).fit(textos[a], y[a]).predict(textos[b])
        res = {n: metricas(y[dif == n], oof[dif == n]) for n in ("facil", "dificil")}
        out.append(f"| {alvo} | {res['facil'][0]} | {res['facil'][1]} | {res['dificil'][0]} | {res['dificil'][1]} |")
        if alvo == "categoria":
            extra.append(f"- Categoria nos tickets **ambíguos** (duas categorias, n={int(amb.sum())}): acurácia {metricas(y[amb], oof[amb])[0]}% "
                         f"(o alvo é a categoria do primeiro problema citado).")
            muito_curtos = np.array([len(r['descricao'].split()) <= 6 for r in t])
            extra.append(f"- Categoria nos tickets **muito curtos** (≤ 6 palavras, n={int(muito_curtos.sum())}): acurácia {metricas(y[muito_curtos], oof[muito_curtos])[0]}%.")
    out += [""] + extra

    classes = sorted(set(cat))
    mc = confusion_matrix(cat[te], pred_cat, labels=classes)
    out += ["\n## Matriz de confusão da categoria (divisão 80/20; linhas = real, colunas = previsto)\n",
            "| real \\ previsto | " + " | ".join(classes) + " |", "|---|" + "---:|" * len(classes)]
    for c, linha in zip(classes, mc):
        out.append(f"| {c} | " + " | ".join(str(int(x)) for x in linha) + " |")
    out += ["\n> Dados sintéticos gerados por banco de cenários: o baseline tende a ir muito bem mesmo no conjunto difícil, "
            "porque o vocabulário dos cenários se repete. Não use estes números como estimativa de desempenho em tickets reais."]
    destino = RAIZ / "validacao" / "baseline_tickets.md"
    destino.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
