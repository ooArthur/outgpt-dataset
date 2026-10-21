"""Exporta os dados de ajuste fino em export/*.jsonl (só a chave `messages`, sem `meta`).

Arquivos gerados (embaralhados com seed da ficha):
  sft_treino_base.jsonl           qa_treino                          (cenários C/D)
  sft_treino_memorizacao.jsonl    qa_treino + qa_memorizacao_treino  (cenários E/F)
  sft_teste.jsonl                 qa_teste
  sft_memorizacao_teste.jsonl     qa_memorizacao_teste

Mistura opcional com dados gerais em português (já convertidos com scripts/converter_instrucoes.py):
  python scripts/exportar_treino.py --mistura geral_ptbr.jsonl --prop 0.2 --saida sft_treino_memorizacao_mix.jsonl [--base base|memorizacao]
`--prop` é a fração de exemplos GERAIS no arquivo final (0.2 = 20%).
"""
import argparse
import json
import random
import sys

from common import RAIZ, carregar_ficha, ler_jsonl

EXPORT = RAIZ / "export"


def so_messages(regs):
    return [{"messages": r["messages"]} for r in regs]


def gravar(nome, regs):
    EXPORT.mkdir(exist_ok=True)
    destino = EXPORT / nome
    with open(destino, "w", encoding="utf-8", newline="\n") as fh:
        for r in regs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return destino


def embaralhado(regs, seed):
    regs = list(regs)
    random.Random(seed).shuffle(regs)
    return regs


def exportar_padrao(seed):
    treino = so_messages(ler_jsonl("qa/qa_treino.jsonl"))
    memo = so_messages(ler_jsonl("qa/qa_memorizacao_treino.jsonl"))
    saidas = {
        "sft_treino_base.jsonl": embaralhado(treino, seed + 51),
        "sft_treino_memorizacao.jsonl": embaralhado(treino + memo, seed + 52),
        "sft_teste.jsonl": so_messages(ler_jsonl("qa/qa_teste.jsonl")),
        "sft_memorizacao_teste.jsonl": so_messages(ler_jsonl("qa/qa_memorizacao_teste.jsonl")),
    }
    for nome, regs in saidas.items():
        d = gravar(nome, regs)
        print(f"export/{nome}: {len(regs)} exemplos ({d.stat().st_size / 1024:.0f} KB)")


def misturar(args, seed):
    if not 0 < args.prop < 1:
        sys.exit("--prop deve estar entre 0 e 1 (fração de exemplos gerais no arquivo final).")
    base = so_messages(ler_jsonl("qa/qa_treino.jsonl"))
    if args.base == "memorizacao":
        base += so_messages(ler_jsonl("qa/qa_memorizacao_treino.jsonl"))
    geral = []
    with open(args.mistura, encoding="utf-8") as fh:
        for i, linha in enumerate(fh, 1):
            if not linha.strip():
                continue
            r = json.loads(linha)
            if not isinstance(r.get("messages"), list):
                sys.exit(f"{args.mistura}:{i}: sem a chave 'messages'. Converta antes com scripts/converter_instrucoes.py.")
            geral.append({"messages": r["messages"]})
    n_geral = round(args.prop / (1 - args.prop) * len(base))
    if len(geral) < n_geral:
        print(f"aviso: só há {len(geral)} exemplos gerais (pedidos {n_geral}); a proporção real será menor.", file=sys.stderr)
    geral = random.Random(seed + 53).sample(geral, min(n_geral, len(geral)))
    mix = embaralhado(base + geral, seed + 54)
    nome = args.saida if args.saida.endswith(".jsonl") else args.saida + ".jsonl"
    d = gravar(nome, mix)
    print(f"export/{nome}: {len(base)} da empresa + {len(geral)} gerais = {len(mix)} ({100 * len(geral) / len(mix):.1f}% gerais, {d.stat().st_size / 1024:.0f} KB)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mistura", help="arquivo .jsonl com dados gerais já no formato messages")
    ap.add_argument("--prop", type=float, default=0.2, help="fração de exemplos gerais no arquivo final (padrão 0.2)")
    ap.add_argument("--saida", default="sft_treino_mistura.jsonl", help="nome do arquivo gerado em export/")
    ap.add_argument("--base", choices=["base", "memorizacao"], default="memorizacao", help="dados da empresa usados na mistura")
    args = ap.parse_args()
    seed = carregar_ficha()["empresa"]["seed"]
    if args.mistura:
        misturar(args, seed)
    else:
        exportar_padrao(seed)


if __name__ == "__main__":
    main()
