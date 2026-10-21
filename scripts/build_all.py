"""Regenera toda a base a partir da ficha-mestra: python scripts/build_all.py"""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ETAPAS = ["gen_data", "render_docs"]  # as demais etapas são adicionadas conforme ficam prontas


def main():
    for nome in ETAPAS:
        print(f"== {nome}")
        mod = importlib.import_module(nome)
        (getattr(mod, "main", None) or (lambda: mod.renderizar_todos()))()


if __name__ == "__main__":
    main()
