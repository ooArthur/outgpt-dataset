"""Regenera toda a base a partir da ficha-mestra: python scripts/build_all.py"""
import importlib
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ETAPAS = ["gen_data", "render_docs", "gen_fatos", "gen_qa", "gen_memorizacao", "gen_avaliacao", "gen_acesso", "gen_tickets", "gen_chunks", "exportar_treino"]


def main():
    for nome in ETAPAS:
        print(f"== {nome}")
        mod = importlib.import_module(nome)
        (getattr(mod, "main", None) or (lambda: mod.renderizar_todos()))()
    print("== rag/avaliar_recuperacao")
    subprocess.check_call([sys.executable, str(Path(__file__).resolve().parent.parent / "rag" / "avaliar_recuperacao.py")], stdout=subprocess.DEVNULL)
    print("== validar")
    raiz = Path(__file__).resolve().parent.parent
    sys.exit(subprocess.call([sys.executable, str(raiz / "validacao" / "validar.py"), "--readme"]))


if __name__ == "__main__":
    main()
