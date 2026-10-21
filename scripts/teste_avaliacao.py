"""Testa o próprio avaliador com modelos falsos (oráculo, vazio, recusa). Uso: python scripts/teste_avaliacao.py"""
import importlib.util
import sys

from common import RAIZ


def _runner():
    spec = importlib.util.spec_from_file_location("rodar_avaliacao", RAIZ / "avaliacao" / "rodar_avaliacao.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rodar():
    r = _runner()
    itens = r.carregar("avaliacao") + r.carregar("acesso") + r.carregar("memorizacao_teste")
    res = {m: r.medias(r.avaliar(itens, lambda it, msgs, m=m: r.simulado(m, it))) for m in ("oraculo", "vazio", "recusa")}
    erros = []

    def metrica(modo, conj, tipo, nome):
        return res[modo][(conj, tipo)][0].get(nome)

    numericos = [("avaliacao", t) for t in ("simples", "numerica", "multi-documento", "versao_antiga_vs_nova")] + [("memorizacao_teste", "memorizacao")]
    # oráculo: ≈100% em tudo
    for chave, (ms, n) in res["oraculo"].items():
        for nome, v in ms.items():
            alvo = 0.0 if nome in ("alucinacao", "vazamento") else 1.0
            if abs(v - alvo) > 0.01:
                erros.append(f"oráculo: {chave} {nome}={v:.2f} (esperado {alvo:.0f})")
    # vazio: ≈0% em tudo que mede acerto
    for chave, (ms, n) in res["vazio"].items():
        for nome, v in ms.items():
            if nome not in ("alucinacao", "vazamento") and v > 0.05:
                erros.append(f"vazio: {chave} {nome}={v:.2f} (esperado ≈0)")
    # recusa: acerta recusas, erra respostas
    for chave in (("avaliacao", "sem_resposta"), ("avaliacao", "fora_de_escopo"), ("acesso", "acesso/negar")):
        nome = {"sem_resposta": "recusa_correta", "fora_de_escopo": "recusa_correta", "acesso/negar": "negou_corretamente"}[chave[1]]
        if metrica("recusa", *chave, nome) < 0.99:
            erros.append(f"recusa: {chave} {nome} deveria ser 100%")
    for chave in numericos:
        if metrica("recusa", *chave, "cobertura_lexical") > 0.35 or (metrica("recusa", *chave, "acerto_numerico") or 0) > 0.05:
            erros.append(f"recusa: {chave} deveria errar (acerto numérico/cobertura altos)")
    if metrica("recusa", "acesso", "acesso/responder", "respondeu_corretamente") > 0.01:
        erros.append("recusa: itens de acesso 'responder' deveriam errar")
    # normalização de números pt-BR
    casos = {"R$ 2.000": {2000.0}, "2000": {2000.0}, "1,5": {1.5}, "R$ 20.000,50": {20000.5}, "30 dias": {30.0}}
    for txt, esp in casos.items():
        if r.numeros(txt) != esp:
            erros.append(f"numeros({txt!r}) = {r.numeros(txt)}, esperado {esp}")
    if r.acerto_numerico("O limite é R$ 2.000.", "o valor é 2000 reais") != 1.0:
        erros.append("acerto_numerico deveria aceitar 'R$ 2.000' == '2000'")
    resumo = {m: {f"{c}/{t}": {k: round(v, 2) for k, v in ms.items()} for (c, t), (ms, n) in d.items()} for m, d in res.items()}
    return erros, {"itens": len(itens), "modos": list(res)}, resumo


if __name__ == "__main__":
    e, s, _ = rodar()
    for x in e:
        print("ERRO:", x)
    print(f"teste_avaliacao: {len(e)} erro(s) | {s}")
    sys.exit(1 if e else 0)
