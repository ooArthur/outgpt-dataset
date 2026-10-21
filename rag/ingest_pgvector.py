"""OPCIONAL: ingere rag/chunks.jsonl em Postgres + pgvector, com embeddings gerados pelo Ollama (/api/embed).

NÃO FOI TESTADO CONTRA UM POSTGRES REAL (não havia Postgres disponível ao escrever). Revise antes de usar.

Pré-requisitos: Postgres com a extensão pgvector, `pip install "psycopg[binary]"` e `ollama pull bge-m3`
(modelo de embedding multilíngue; `embeddinggemma` também serve — use o MESMO modelo para indexar e consultar).
A dimensão do vetor é descoberta a partir da primeira resposta do Ollama, sem valor fixo no código.

Exemplos:
  python rag/ingest_pgvector.py --dsn postgresql://postgres:postgres@localhost:5432/brisa --recriar
  python rag/ingest_pgvector.py --dsn ... --consulta "Quantos dias de home office?" --perfil colaborador
A coluna `acesso` guarda o nível do documento; a consulta filtra pelos níveis do perfil (ficha-mestra/acesso.yaml).
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))


def embeddings(url, modelo, textos):
    req = urllib.request.Request(f"{url.rstrip('/')}/api/embed", data=json.dumps({"model": modelo, "input": textos}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)["embeddings"]
    except urllib.error.URLError as e:
        sys.exit(f"Não consegui falar com o Ollama em {url} ({e}). Ele está rodando e o modelo '{modelo}' foi baixado (ollama pull {modelo})?")


def vetor(v):
    return "[" + ",".join(f"{x:.7f}" for x in v) + "]"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dsn", default=os.environ.get("PGDSN"), help="string de conexão (ou variável PGDSN)")
    ap.add_argument("--modelo", default="bge-m3")
    ap.add_argument("--ollama-url", default="http://localhost:11434")
    ap.add_argument("--tabela", default="chunks_brisa")
    ap.add_argument("--lote", type=int, default=32)
    ap.add_argument("--recriar", action="store_true", help="apaga e recria a tabela")
    ap.add_argument("--consulta", help="em vez de ingerir, busca os 4 chunks mais próximos")
    ap.add_argument("--perfil", default="diretoria")
    args = ap.parse_args()
    if not args.dsn:
        sys.exit("Informe --dsn (ou a variável de ambiente PGDSN).")
    try:
        import psycopg
    except ImportError:
        sys.exit('Falta o psycopg. Instale com: pip install -r requirements-opcional.txt  (ou pip install "psycopg[binary]")')
    tabela = args.tabela
    if not tabela.replace("_", "").isalnum():
        sys.exit("--tabela deve conter apenas letras, números e _.")

    with psycopg.connect(args.dsn) as con:
        if args.consulta:
            from acesso import niveis_do_perfil
            q = embeddings(args.ollama_url, args.modelo, [args.consulta])[0]
            linhas = con.execute(f"SELECT chunk_id, fonte_doc, left(texto, 120), embedding <=> %s::vector AS dist FROM {tabela} "
                                 f"WHERE acesso = ANY(%s) ORDER BY dist LIMIT 4", (vetor(q), sorted(niveis_do_perfil(args.perfil)))).fetchall()
            for r in linhas:
                print(f"{r[3]:.4f}  {r[1]}  [{r[0]}]  {r[2]!r}")
            return
        chunks = [json.loads(l) for l in (RAIZ / "rag" / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        dim = len(embeddings(args.ollama_url, args.modelo, [chunks[0]["texto"]])[0])
        con.execute("CREATE EXTENSION IF NOT EXISTS vector")
        if args.recriar:
            con.execute(f"DROP TABLE IF EXISTS {tabela}")
        con.execute(f"CREATE TABLE IF NOT EXISTS {tabela} (chunk_id text PRIMARY KEY, fonte_doc text, titulo text, area text, versao text, "
                    f"vigencia text, acesso text NOT NULL, status text, texto text, embedding vector({dim}))")
        for i in range(0, len(chunks), args.lote):
            lote = chunks[i:i + args.lote]
            vs = embeddings(args.ollama_url, args.modelo, [c["titulo"] + "\n" + c["texto"] for c in lote])
            for c, v in zip(lote, vs):
                con.execute(f"INSERT INTO {tabela} VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector) ON CONFLICT (chunk_id) DO UPDATE "
                            f"SET texto = EXCLUDED.texto, embedding = EXCLUDED.embedding, acesso = EXCLUDED.acesso, status = EXCLUDED.status",
                            (c["chunk_id"], c["fonte_doc"], c["titulo"], c["area"], c["versao"], c["vigencia"], c["acesso"], c["status"],
                             c["texto"], vetor(v)))
            print(f"{min(i + args.lote, len(chunks))}/{len(chunks)}")
        con.execute(f"CREATE INDEX IF NOT EXISTS {tabela}_acesso ON {tabela} (acesso)")
        con.execute(f"CREATE INDEX IF NOT EXISTS {tabela}_emb ON {tabela} USING hnsw (embedding vector_cosine_ops)")
    print(f"ok: {len(chunks)} chunks em {tabela} (dimensão {dim}).")


if __name__ == "__main__":
    main()
