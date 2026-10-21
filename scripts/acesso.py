"""Filtro de acesso determinístico: decide quais fontes cada perfil pode ver (aplicado ANTES do RAG)."""
import functools

import yaml

from common import RAIZ, ler_doc, ler_jsonl


@functools.lru_cache(maxsize=1)
def matriz():
    with open(RAIZ / "ficha-mestra" / "acesso.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@functools.lru_cache(maxsize=1)
def _sensibilidade_por_fonte_nos_fatos():
    por_fonte = {}
    for f in ler_jsonl("fatos/fatos.jsonl"):
        por_fonte.setdefault(f["fonte_doc"], set()).add(f["sensibilidade"])
    return por_fonte


def acesso_da_fonte(rel):
    """Nível de acesso de uma fonte. .md: front matter; CSV: deduzido dos fatos (falha se houver mais de um nível)."""
    if rel.endswith(".md"):
        return ler_doc(rel)[0]["acesso"]
    niveis = _sensibilidade_por_fonte_nos_fatos().get(rel, set())
    if len(niveis) > 1:
        raise ValueError(f"{rel}: fatos com mais de uma sensibilidade {sorted(niveis)}")
    if niveis:
        return next(iter(niveis))
    try:
        return matriz()["fontes_csv"][rel]
    except KeyError:
        raise ValueError(f"{rel}: sem nível de acesso (nenhum fato e fora de fontes_csv)") from None


def niveis_do_perfil(perfil):
    try:
        return set(matriz()["perfis"][perfil])
    except KeyError:
        raise ValueError(f"perfil desconhecido: {perfil!r} (válidos: {sorted(matriz()['perfis'])})") from None


def pode_ver(perfil, rel):
    return acesso_da_fonte(rel) in niveis_do_perfil(perfil)


def fontes_permitidas(perfil):
    fontes = sorted(p.relative_to(RAIZ).as_posix() for p in (RAIZ / "docs").glob("*/*.md"))
    fontes += sorted(matriz()["fontes_csv"])
    return [f for f in fontes if pode_ver(perfil, f)]


def filtrar_trechos(perfil, trechos):
    """trechos: lista de (fonte_doc, texto) — devolve só os que o perfil pode ver."""
    return [(rel, txt) for rel, txt in trechos if pode_ver(perfil, rel)]


def mensagem_negado(area_txt):
    return matriz()["mensagem_negado"].format(area=area_txt)
