"""Gera rag/chunks.jsonl: trechos dos documentos e do diretório, no mesmo formato de contexto visto no treino."""
from common import AREAS_DOC, RAIZ, escrever_jsonl, ler_csv, linha_diretorio, slug
from gen_qa import Contextos


def main():
    ctxs = Contextos()
    chunks = []
    for area in AREAS_DOC:
        for p in sorted((RAIZ / "docs" / area).glob("*.md")):
            rel = p.relative_to(RAIZ).as_posix()
            meta, trechos = ctxs.chunks(rel)
            for i, t in enumerate(trechos, 1):
                chunks.append({"chunk_id": f"{area}-{p.stem}-{i:02d}", "fonte_doc": rel, "titulo": meta["titulo"], "area": area,
                               "versao": str(meta["versao"]), "vigencia": str(meta["vigencia"]), "acesso": meta["acesso"],
                               "status": meta.get("status", "vigente"), "texto": t})
    func = ler_csv("data/funcionarios.csv")
    por_id = {f["id"]: f for f in func}
    for f in func:
        chunks.append({"chunk_id": f"diretorio-{int(f['id']):03d}", "fonte_doc": "data/funcionarios.csv", "titulo": "Diretório de colaboradores",
                       "area": "institucional", "versao": "2026", "vigencia": "2026-01-01", "acesso": "publico", "status": "vigente",
                       "texto": linha_diretorio(f, por_id)})
    escrever_jsonl("rag/chunks.jsonl", chunks)
    print(f"rag/chunks.jsonl: {len(chunks)} chunks ({len(chunks) - len(func)} de documentos, {len(func)} do diretório)")


if __name__ == "__main__":
    main()
