"""Converte dados de instrução (formato Alpaca: instruction/input/output) para o formato `messages`.

Uso:
  python scripts/converter_instrucoes.py ARQUIVO.jsonl|ARQUIVO.parquet --saida geral_ptbr.jsonl [--limite 5000] [--seed 1]

Funciona com Canarim-Instruct-PTBR e similares. O download é MANUAL (veja o README, seção "Exportação para treino"); nada é baixado aqui.
.parquet exige pandas e pyarrow (pip install -r requirements-opcional.txt). Se as colunas não existirem, o script lista as encontradas e para.
"""
import argparse
import json
import random
import sys

SYSTEM_NEUTRO = "Você é um assistente prestativo."
COLUNAS = ("instruction", "input", "output")


def ler_registros(caminho):
    if caminho.endswith(".parquet"):
        try:
            import pandas as pd
        except ImportError:
            sys.exit("Ler .parquet exige pandas e pyarrow. Instale com: pip install -r requirements-opcional.txt")
        try:
            return pd.read_parquet(caminho).to_dict(orient="records")
        except ImportError:
            sys.exit("Ler .parquet exige pyarrow. Instale com: pip install -r requirements-opcional.txt")
    with open(caminho, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivo", help=".jsonl ou .parquet local")
    ap.add_argument("--saida", required=True, help="arquivo .jsonl de saída (formato messages)")
    ap.add_argument("--limite", type=int, default=None, help="máximo de exemplos (amostra com seed)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--system", default=SYSTEM_NEUTRO, help="system prompt neutro usado nos exemplos")
    args = ap.parse_args()

    regs = ler_registros(args.arquivo)
    if not regs:
        sys.exit("Arquivo vazio.")
    encontradas = sorted(regs[0].keys())
    faltam = [c for c in ("instruction", "output") if c not in regs[0]]
    if faltam:
        sys.exit(f"Colunas ausentes: {faltam}. Colunas encontradas: {encontradas}. Esperado: {list(COLUNAS)} (input é opcional).")
    if args.limite and len(regs) > args.limite:
        regs = random.Random(args.seed).sample(regs, args.limite)
    n = 0
    with open(args.saida, "w", encoding="utf-8", newline="\n") as out:
        for r in regs:
            instr, extra, resp = str(r.get("instruction") or "").strip(), str(r.get("input") or "").strip(), str(r.get("output") or "").strip()
            if not instr or not resp:
                continue
            user = f"{instr}\n\n{extra}" if extra and extra.lower() != "nan" else instr
            out.write(json.dumps({"messages": [{"role": "system", "content": args.system}, {"role": "user", "content": user},
                                               {"role": "assistant", "content": resp}]}, ensure_ascii=False) + "\n")
            n += 1
    print(f"{n} exemplos gravados em {args.saida}")


if __name__ == "__main__":
    main()
