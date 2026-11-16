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

import re

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
    itens: list[dict] = []
    atual, artigo, total = None, None, None
    for linha in linhas:
        v = [x for x in linha if str(x).strip() != ""]
        if not v:
            continue
        a = str(v[0])
        if a.startswith("Documento:"):
            tipo, numero = [x.strip() for x in a.split(":", 1)[1].split(" - ", 1)]
            atual = (tipo.upper(), numero)
        elif a.startswith("Artigo:"):
            cod, _, nome = a.split(":", 1)[1].strip().partition(" - ")
            artigo = (cod.strip(), nome.strip())
        elif a.startswith("Total: "):
            total = float(v[-1])
        elif a.startswith("Total"):
            continue
        elif atual and len(v) == 6 and all(isinstance(x, float) for x in v[2:]):
            codigo = str(v[0]).removesuffix(".0")
            if artigo:
                itens.append({"tipo": atual[0], "numero": atual[1], "ano": atual[1][:4], "artigo": artigo[0],
                              "nome_artigo": artigo[1], "vendedor": codigo, "quantidade": v[2], "bruto": v[3],
                              "desconto": v[4], "liquido": v[5]})
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
    return {"documentos": documentos, "itens": itens, "total_relatorio": total, "soma": soma,
            "confere": total is None or abs(soma - total) < 0.01}


def ler_xls(caminho: Path) -> dict:
    return ler_linhas(_linhas_xls(Path(caminho)))


def ler_datas_linhas(linhas) -> dict:
    """Relatório "Análise de Vendas — Documento": abreviatura, nº, data, qtd, valor, desconto, líquido."""
    import re

    datas, valores, total, soma = {}, {}, None, 0.0
    for linha in linhas:
        v = [x for x in linha if str(x).strip() != ""]
        if len(v) == 7 and re.fullmatch(r"\d{2}/\d{2}/\d{4}", str(v[2]).strip()):
            d, m, a = str(v[2]).strip().split("/")
            chave = (str(v[0]).strip().upper(), str(v[1]).strip())
            datas[chave] = f"{a}-{m}-{d}"
            valores[chave] = float(v[6])
            soma += v[6]
        elif v and str(v[0]).startswith("Total: "):
            total = float(v[-1])
    return {"datas": datas, "valores": valores, "total_relatorio": total, "soma": round(soma, 2),
            "confere": total is None or abs(soma - total) < 0.01}


def ler_datas_xls(caminho: Path) -> dict:
    return ler_datas_linhas(_linhas_xls(Path(caminho)))


# ----------------------------------------- "Vendedor, Zona resumido a Tipo de Entidade" (tipo de cliente e zona)
# Os códigos de tipo de entidade mudaram do ERP19 para o ERP22 (ex.: 4 = LIVRARIA no ERP19, EMPRESAS no ERP22);
# por isso o segmento vem da DESCRIÇÃO, alinhado com as linhas de atendimento da loja.
SEGMENTOS = [
    ("Igrejas", ("IGREJA",)),
    ("Livrarias e revendedores", ("LIVRARIA", "REVENDEDOR")),
    ("Empresas e instituições", ("EMPRESA", "INSTITUI")),
    ("Retalho (clientes, VIP, pastores, missionários)", ("CLIENTE", "PASTOR", "MISSION")),
]


def canal(descricao: str) -> str:
    """Varejo: cliente, cliente VIP, pastor, missionário. Atacado (compras a grosso): livrarias, igrejas,
    revendedores, pastor revendedor, empresas e instituições. Sem tipo: N/D (fica fora dos dois)."""
    s = segmento(descricao)
    if s.startswith("Retalho"):
        return "Varejo"
    return "Sem tipo (N/D)" if s.startswith("Sem tipo") else "Atacado"


def segmento(descricao: str) -> str:
    d = descricao.upper()
    if "PASTOR REVENDEDOR" in d or "EBD/ LIVRARIA" in d or "EBD/LIVRARIA" in d:
        return "Livrarias e revendedores"
    for nome, chaves in SEGMENTOS:
        if any(c in d for c in chaves):
            return nome
    return "Sem tipo (N/D)"


def ler_zonas_linhas(linhas) -> dict:
    registos, vendedor, zona, total = [], None, None, None
    for linha in linhas:
        v = [x for x in linha if str(x).strip() != ""]
        if not v:
            continue
        a = str(v[0])
        if a.startswith("Vendedor:"):
            vendedor = a.split(":", 1)[1].strip()
        elif a.startswith("Zona:"):
            zona = a.split(":", 1)[1].strip()
        elif a.startswith("Total: "):
            total = float(v[-1])
        elif a.startswith("Total"):
            continue
        elif vendedor and zona and len(v) == 6 and all(isinstance(x, float) for x in v[2:]):
            codigo, _, nome_vend = vendedor.partition(" - ")
            registos.append({"vendedor": codigo.strip(), "nome_vendedor": (nome_vend or codigo).strip(),
                             "zona": zona.split(" - ", 1)[-1].strip().title(), "tipo": str(v[1]).strip(),
                             "segmento": segmento(str(v[1])), "quantidade": v[2], "bruto": v[3],
                             "desconto": v[4], "liquido": v[5]})
    soma = round(sum(r["liquido"] for r in registos), 2)
    return {"registos": registos, "total_relatorio": total, "soma": soma,
            "confere": total is None or abs(soma - total) < 0.01}


def ler_zonas_xls(caminho: Path) -> dict:
    return ler_zonas_linhas(_linhas_xls(Path(caminho)))


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


# ---- Análise de Vendas agrupada por «Documento» exportada em PDF (texto do pypdf)
# Linha: "<qtd com 3 decimais><nº documento>  <líquido> <desconto> <valor><tipo> <data>"; o tipo pode vir partido.
_NUM_PDF = r"-?\d{1,3}(?:[   ]\d{3})*,\d{2}"
_DOC_PDF = re.compile(rf"(-?[\d ]+,\d{{3}})(\d{{4}}-\d+)\s+({_NUM_PDF})\s*({_NUM_PDF})\s+({_NUM_PDF})\s*([A-Z/]+?)\s*"
                      r"(?:\n\s*)?([A-Z/]*)\s*(\d{2})/(\d{2})/(\d{4})")


def ler_documentos_pdf(texto: str) -> dict:
    """{documentos: [{tipo, numero, data, liquido, desconto, quantidade}], total, soma, confere}."""
    num = lambda x: float(re.sub(r"[   ]", "", x).replace(",", "."))
    docs = []
    for m in _DOC_PDF.finditer(texto):
        docs.append({"tipo": (m.group(6) + m.group(7)).upper(), "numero": m.group(2),
                     "data": f"{m.group(10)}-{m.group(9)}-{m.group(8)}", "liquido": num(m.group(3)),
                     "desconto": num(m.group(4)), "quantidade": num(m.group(1))})
    t = re.search(rf"({_NUM_PDF})\s*{_NUM_PDF}\s+{_NUM_PDF}\s+[\d ]+,\d{{3}}Total:", texto)
    soma = round(sum(d["liquido"] for d in docs), 2)
    total = num(t.group(1)) if t else None
    return {"documentos": docs, "total": total, "soma": soma, "confere": total is not None and abs(soma - total) < 0.05}
