"""Utilitários compartilhados: caminhos, ficha-mestra, formatação pt-BR e datas."""
import csv
import datetime as dt
import json
import re
import unicodedata
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
FICHA = RAIZ / "ficha-mestra" / "empresa.yaml"
RODAPE = "Documento fictício, criado para fins acadêmicos."
SYSTEM_PROMPT = (
    "Você é o OutGPT, assistente interno da Brisa Log. Responda em português do Brasil, "
    "de forma clara e cordial, usando apenas as informações da empresa. Se não souber, "
    "diga que não encontrou e indique a área responsável."
)
AREAS_DOC = ["institucional", "rh", "financeiro", "ti", "comercial", "compliance"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def carregar_ficha():
    with open(FICHA, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def ler_csv(caminho):
    with open(RAIZ / caminho, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def escrever_csv(caminho, campos, linhas):
    destino = RAIZ / caminho
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)


def escrever_jsonl(caminho, registros):
    destino = RAIZ / caminho
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="\n") as fh:
        for r in registros:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def ler_jsonl(caminho):
    with open(RAIZ / caminho, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


# ------------------------------------------------------------ formatação pt-BR
def _milhar(n, casas=0):
    s = f"{n:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def brl(valor):
    """R$ 2.000 para inteiros; R$ 1.234,56 quando há centavos."""
    valor = float(valor)
    sinal = "-" if valor < 0 else ""
    valor = abs(valor)
    if abs(valor - round(valor)) < 1e-9:
        return sinal + "R$ " + _milhar(round(valor))
    return sinal + "R$ " + _milhar(valor, 2)


def brl2(valor):
    """Sempre com centavos: R$ 68,00."""
    return "R$ " + _milhar(float(valor), 2)


def num(valor, casas=0):
    return _milhar(float(valor), casas)


def milhoes(valor):
    return "R$ " + _milhar(valor / 1_000_000, 1) + " milhões"


def pct(valor, casas=0):
    return _milhar(float(valor), casas) + "%"


def sem_acento(txt):
    return unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()


def slug(txt):
    return re.sub(r"[^a-z0-9]+", "-", sem_acento(txt).lower()).strip("-")


def normaliza(txt):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", sem_acento(txt).lower())).strip()


# ------------------------------------------------------------ datas
def dia_util_n(ano, mes, n, feriados):
    """n-ésimo dia útil do mês (segunda a sexta, sem feriados nacionais da ficha)."""
    fer = {dt.date.fromisoformat(d) for d in feriados}
    d = dt.date(ano, mes, 1)
    cont = 0
    while True:
        if d.weekday() < 5 and d not in fer:
            cont += 1
            if cont == n:
                return d
        d += dt.timedelta(days=1)


def data_br(d):
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


def dia_semana(d):
    return ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
            "sexta-feira", "sábado", "domingo"][d.weekday()]


def trimestres_fin():
    """Lista ordenada de rótulos '2024T1'... do CSV financeiro."""
    return [l["trimestre"] for l in ler_csv("data/financeiro_trimestral.csv")]


# ------------------------------------------------------------ documentos
def ler_doc(rel):
    """Lê docs/.../x.md e devolve (meta, corpo). rel é relativo à raiz do repositório."""
    texto = (RAIZ / rel).read_text(encoding="utf-8")
    _, fm, corpo = texto.split("---", 2)
    return yaml.safe_load(fm), corpo.strip()


def chunks_doc(rel):
    """Divide o corpo do documento em trechos por título (para contexto de RAG)."""
    meta, corpo = ler_doc(rel)
    blocos, atual = [], []
    for linha in corpo.splitlines():
        if linha.startswith("#") and atual:
            blocos.append("\n".join(atual).strip())
            atual = []
        atual.append(linha)
    if atual:
        blocos.append("\n".join(atual).strip())
    return meta, [b for b in blocos if len(b.split()) >= 8]
