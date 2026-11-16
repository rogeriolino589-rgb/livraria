"""Leitura do relatório "Análise de Vendas — Documento, Artigo resumido a Vendedor" do Eticadata (ERP19 e ERP22).

O Eticadata exporta este mapa (Crystal Reports) para .xls, repartido por várias folhas de 65 mil linhas:

    Documento: V/DIN - 2025-000123
    Artigo: 174057 - BIBLIA DE ESTUDO ...
    2   Sergio Guacha   1.0   5800.0   -580.0   5220.0      <- vendedor, nome, qtd, valor, desconto, líquido
    Total Artigo: ...
    Total Documento: ...
    ...
    Total:  82237524.02                                      <- total geral (serve para conferir)

`ler_xls()` devolve um registo por documento (tipo, número, ano, vendedor, nome, valores) e o total geral do relatório.
`resumo()` junta por ano e vendedor: nº de documentos de venda, valor vendido, devoluções e ticket médio.
"""

from __future__ import annotations

import collections
from pathlib import Path

TIPOS_VENDA = {"V/DIN", "FACT", "TAL"}  # venda a dinheiro, fatura, talão; DEVOL e N/CRE são devoluções/créditos


def _linhas_xls(caminho: Path):
    import xlrd

    livro = xlrd.open_workbook(str(caminho), on_demand=True)
    for i in range(livro.nsheets):
        folha = livro.sheet_by_index(i)
        for r in range(folha.nrows):
            yield folha.row_values(r)


def ler_linhas(linhas) -> dict:
    """Interpreta as linhas do relatório (listas de células, já sem formatação)."""
    docs: dict[tuple, dict] = {}
    atual, total = None, None
    for linha in linhas:
        v = [x for x in linha if str(x).strip() != ""]
        if not v:
            continue
        a = str(v[0])
        if a.startswith("Documento:"):
            tipo, numero = [x.strip() for x in a.split(":", 1)[1].split(" - ", 1)]
            atual = (tipo.upper(), numero)
        elif a.startswith("Total: "):
            total = float(v[-1])
        elif a.startswith(("Artigo:", "Total")):
            continue
        elif atual and len(v) == 6 and all(isinstance(x, float) for x in v[2:]):
            codigo = str(v[0]).removesuffix(".0")
            d = docs.setdefault(atual, {"tipo": atual[0], "numero": atual[1], "ano": atual[1][:4],
                                        "por_vendedor": collections.Counter(), "nomes": {},
                                        "quantidade": 0.0, "bruto": 0.0, "desconto": 0.0, "liquido": 0.0})
            d["por_vendedor"][codigo] += v[5]
            d["nomes"][codigo] = str(v[1])
            for campo, valor in zip(("quantidade", "bruto", "desconto", "liquido"), v[2:]):
                d[campo] += valor
    documentos = []
    for d in docs.values():
        vendedor = max(d["por_vendedor"], key=lambda k: abs(d["por_vendedor"][k]))
        documentos.append({"tipo": d["tipo"], "numero": d["numero"], "ano": d["ano"], "vendedor": vendedor,
                           "nome_vendedor": d["nomes"][vendedor], "vendedores": len(d["por_vendedor"]),
                           **{c: round(d[c], 2) for c in ("quantidade", "bruto", "desconto", "liquido")}})
    soma = round(sum(d["liquido"] for d in documentos), 2)
    return {"documentos": documentos, "total_relatorio": total, "soma": soma,
            "confere": total is None or abs(soma - total) < 0.01}


def ler_xls(caminho: Path) -> dict:
    return ler_linhas(_linhas_xls(Path(caminho)))


def resumo(documentos: list[dict], nomes: dict[str, str] | None = None) -> list[dict]:
    """Por ano e vendedor. `nomes` substitui o nome do relatório (ex.: {"3": "José Tovela (INATIVO)"})."""
    nomes = nomes or {}
    grupos: dict[tuple, dict] = {}
    for d in documentos:
        nome = nomes.get(d["vendedor"], d["nome_vendedor"])
        g = grupos.setdefault((d["ano"], d["vendedor"]), {"ano": d["ano"], "vendedor": d["vendedor"], "nome": nome,
                                                            "documentos": 0, "vendas": 0.0, "devolucoes": 0.0,
                                                            "descontos": 0.0})
        if d["tipo"] in TIPOS_VENDA:
            g["documentos"] += 1
            g["vendas"] += d["liquido"]
            g["descontos"] += d["desconto"]
        else:
            g["devolucoes"] += d["liquido"]
    linhas = sorted(grupos.values(), key=lambda g: (g["ano"], -g["vendas"]))
    for g in linhas:
        g["ticket_medio"] = round(g["vendas"] / g["documentos"], 2) if g["documentos"] else 0.0
        for c in ("vendas", "devolucoes", "descontos"):
            g[c] = round(g[c], 2)
    return linhas
