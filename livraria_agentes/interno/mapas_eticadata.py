"""Leitura dos mapas diários do Eticadata (ERP19/ERP22) que a loja envia por e-mail.

Dois relatórios, em PDF, chegam todos os dias no e-mail "Resumo de vendas diário":
  * Diário de Vendas por Tipo de Documento (DiarioVendasTpDoc.Rpt): uma linha por documento
    (data, documento V/DIN AAAA-NNNNNN, vendedor, meio de pagamento, mercadoria, descontos, IVA, total)
    e o quadro de impostos (código 1 = isento 0 %, código 3 = IVA 16 %).
  * Mapa de Caixa (Caixa.rpt): abertura (fundo de caixa), movimentos por meio de pagamento
    (Dinheiro, Ponto 24, ...) e o resumo do fecho (vendas, descontos, anuladas, nº de vendas, venda média).

As funções recebem o TEXTO do PDF (o Outlook/`read_resource` já o devolve assim; pypdf também serve)
e não alteram nada. `conferir()` cruza os dois mapas: o total do diário tem de bater com o caixa.
"""

from __future__ import annotations

import re
from datetime import datetime

NUM = r"-?\d{1,3}(?:\.\d{3})*,\d{2}"  # formato do Eticadata: 1.234,56


def configuracao() -> dict:
    """config/eticadata.json: nomes dos vendedores por código e meios de pagamento."""
    import json

    from ..pais import _achar

    arq = _achar("config/eticadata.json")
    return json.loads(arq.read_text(encoding="utf-8")) if arq and arq.exists() else {}


def nome_vendedor(codigo: str, config: dict | None = None) -> str:
    nome = (config if config is not None else configuracao()).get("vendedores", {}).get(str(codigo))
    return f"{nome} ({codigo})" if nome else str(codigo)


def _n(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", "."))


def _data(texto: str) -> str:
    return datetime.strptime(texto, "%d/%m/%Y").date().isoformat()


# ------------------------------------------------------------------ Diário de Vendas
_DOC = re.compile(
    rf"(?P<data>\d{{2}}/\d{{2}}/\d{{4}})\s+(?P<doc>[A-Z]{{1,4}}/[A-Z]{{1,6}}\s+\d{{4}}-\d{{3,}})\s+(?P<vend>\d+)\s+"
    rf"(?P<meio>[^\d\-][^\n]*?)\s+(?P<merc>{NUM})\s+(?P<desc>{NUM})\s+(?P<imp>{NUM})\s+(?P<acer>{NUM})\s+"
    rf"(?P<total>{NUM})\s+(?P<pago>{NUM})\s+(?P<arred>{NUM})")
_IMPOSTOS = re.compile(rf"Quadro Resumo d[oe]s? Impostos.*?Taxa\s+((?:\d+\s+{NUM}\s+{NUM}\s+{NUM}\s*)+)", re.S)
_TAXA = re.compile(rf"(\d+)\s+({NUM})\s+({NUM})\s+({NUM})")


def ler_diario_vendas(texto: str) -> dict:
    """Documentos do Diário de Vendas. Os documentos repetidos noutra página contam uma vez."""
    documentos, vistos = [], set()
    for m in _DOC.finditer(texto):
        if m.group("doc") in vistos:
            continue
        vistos.add(m.group("doc"))
        documentos.append({
            "data": _data(m.group("data")), "documento": re.sub(r"\s+", " ", m.group("doc")),
            "vendedor": m.group("vend"), "meio_pagamento": m.group("meio").strip(),
            "mercadoria": _n(m.group("merc")), "descontos": _n(m.group("desc")), "impostos": _n(m.group("imp")),
            "total": _n(m.group("total")), "valor_pago": _n(m.group("pago")), "arredondamento": _n(m.group("arred"))})
    impostos = []
    q = _IMPOSTOS.search(texto)
    if q:
        impostos = [{"codigo": c, "taxa": _n(t), "incidencia": _n(i), "imposto": _n(v)}
                    for c, t, i, v in _TAXA.findall(q.group(1))]
    seccao = re.search(r"Secção:\s*(\S+)", texto)
    total = round(sum(d["total"] for d in documentos), 2)
    return {"seccao": seccao.group(1) if seccao else None, "documentos": documentos, "total": total,
            "descontos": round(sum(d["descontos"] for d in documentos), 2),
            "impostos": impostos, "por_meio_pagamento": _somar(documentos, "meio_pagamento"),
            "por_vendedor": _somar(documentos, "vendedor")}


def _somar(documentos: list[dict], campo: str) -> dict:
    somas: dict[str, float] = {}
    for d in documentos:
        somas[d[campo]] = round(somas.get(d[campo], 0) + d["total"], 2)
    return somas


# ------------------------------------------------------------------------ Mapa de Caixa
RESUMO_CAIXA = ["Abertura de Caixa", "Entradas / Saídas de Caixa", "Sinal Encomendas", "Devolução de Sinal de Enc.",
                "Enc. Anuladas", "Vendas Anuladas", "Devoluções", "Regulariz(ChqOferta/Cartões)", "Vendas",
                "Cheques-Oferta Emitidos", "Cheques-Oferta Recebidos", "Carreg. Cartões Pré Pagos",
                "Cartões Pré Pagos Utilizados", "Amostras Emitidas", "Descontos", "Movimentos Conta Corrente",
                "Vendas a Crédito", "Recebimentos", "Vales Emitidos", "Vales Recebidos", "Nº Vendas", "Venda Média"]


def ler_mapa_caixa(texto: str) -> dict:
    data = re.search(r"Data:\s*(\d{2}/\d{2}/\d{4})", texto)
    posto = re.search(r"Posto:\s*(\S+)", texto)
    abertura = re.search(rf"Abertura de Caixa Num\.:\s*(\S+).*?({NUM})", texto, re.S)
    movimentos = {}
    bloco = re.search(r"Movimentos do Dia.*?Cheques-Oferta\s+(.*?)\s+Soma:", texto, re.S)
    if bloco:
        # "5.462,00 Dinheiro 22.431,00 Ponto 24": o nome do meio pode ter algarismos (Ponto 24), mas não vírgula decimal.
        movimentos = {meio.strip(): _n(valor) for valor, meio in re.findall(rf"({NUM})\s+(.+?)(?=\s+{NUM}|\s*$)",
                                                                             bloco.group(1).strip())}
    resumo = {}
    fecho = texto.split("Fecho do Caixa", 1)[-1]
    for rotulo in RESUMO_CAIXA:
        m = re.search(re.escape(rotulo) + rf"\s+({NUM})", fecho)
        if m:
            resumo[rotulo] = _n(m.group(1))
    return {"data": _data(data.group(1)) if data else None, "posto": posto.group(1) if posto else None,
            "abertura_num": abertura.group(1) if abertura else None,
            "fundo_caixa": _n(abertura.group(2)) if abertura else None,
            "movimentos": movimentos, "total_movimentos": round(sum(movimentos.values()), 2), "resumo": resumo}


def conferir(diario: dict, caixa: dict) -> list[str]:
    """Diferenças entre o Diário de Vendas e o Mapa de Caixa do mesmo dia (lista vazia = tudo bate)."""
    avisos = []
    vendas = caixa["resumo"].get("Vendas")
    if vendas is not None and abs(vendas - diario["total"]) > 0.01:
        avisos.append(f"Vendas no caixa {vendas:.2f} ≠ total dos documentos {diario['total']:.2f}")
    if abs(caixa["total_movimentos"] - diario["total"]) > 0.01:
        avisos.append(f"Movimentos do caixa {caixa['total_movimentos']:.2f} ≠ total dos documentos {diario['total']:.2f}")
    n = caixa["resumo"].get("Nº Vendas")
    if n is not None and int(n) != len(diario["documentos"]):
        avisos.append(f"Nº de vendas no caixa {int(n)} ≠ {len(diario['documentos'])} documentos no diário")
    desc = caixa["resumo"].get("Descontos")
    if desc is not None and abs(desc - abs(diario["descontos"])) > 0.01:
        avisos.append(f"Descontos no caixa {desc:.2f} ≠ {abs(diario['descontos']):.2f} no diário")
    datas = {d["data"] for d in diario["documentos"]}
    if caixa["data"] and datas and datas != {caixa["data"]}:
        avisos.append(f"Datas diferentes: caixa {caixa['data']}, diário {sorted(datas)}")
    return avisos
