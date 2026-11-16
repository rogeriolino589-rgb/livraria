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

# ERP22 escreve 1.234,56; o ERP19 (2016–jul/2022) escreve 1,234.56. Os dois formatos são aceites.
NUM = r"-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2}"


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
    """O separador decimal é o que está antes dos 2 últimos algarismos; o outro é de milhares."""
    texto = texto.strip()
    return float(re.sub(r"[.,]", "", texto[:-3]) + "." + texto[-2:])


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


# ---- Diário de Vendas de um período longo (ex.: 01/08/2022 a 16/11/2026, centenas de páginas)
# Formato diferente do diário diário: milhares com espaço ("6 490,00") e tipos sem barra (DEVOL).
_NUM_P = r"-?\d{1,3}(?:[   ]\d{3})*,\d{2}"
_LINHA_P = re.compile(
    rf"^(\d{{2}}/\d{{2}}/\d{{4}})\s+(\S+)\s+(\d{{4}}-\d+)\s+(?:(\d+|N/D)\s+)?(.*?)\s*"
    + r"\s+".join([f"({_NUM_P})"] * 7) + r"\s*$")

# meio de pagamento do Eticadata -> forma de pagamento do Financeiro do superapp
FORMAS_FINANCEIRO = {
    "Dinheiro": "Dinheiro", "Numerário Meticais": "Dinheiro", "Ponto 24": "Cartão / POS",
    "Transferência": "Transferência bancária", "Cheque": "Cheque",
    "Crédito Conta Corrente": "Crédito (conta corrente)",
}


def forma_financeiro(meio: str) -> str:
    """Um meio só vai para a forma equivalente; meios combinados («Dinheiro / Ponto 24») ficam como «Misto: …»,
    porque o diário só traz o total do documento e não a parte paga em cada meio."""
    meio = (meio or "").strip()
    if meio in FORMAS_FINANCEIRO:
        return FORMAS_FINANCEIRO[meio]
    if "/" in meio:
        return "Misto: " + " + ".join(FORMAS_FINANCEIRO.get(p.strip(), p.strip()) for p in meio.split("/"))
    return meio or "Por confirmar"


def ler_diario_periodo(texto: str) -> dict:
    """Documentos do Diário de Vendas de um período: {(tipo, numero): {data, vendedor, meio, total, pago}}
    e o «Subtotal» (Total Doc. das vendas menos devoluções) para conferir. O «Total:» do relatório é o valor pago."""
    num = lambda x: float(re.sub(r"[   ]", "", x).replace(",", "."))
    docs, nao_lidas = {}, []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not re.match(r"\d{2}/\d{2}/\d{4}\s", linha):
            continue
        m = _LINHA_P.match(linha)
        if not m:
            nao_lidas.append(linha)
            continue
        v = [num(m.group(i)) for i in range(6, 13)]
        docs[(m.group(2).upper(), m.group(3))] = {
            "data": _data(m.group(1)), "vendedor": m.group(4) or "N/D", "meio": m.group(5).strip(),
            "mercadoria": v[0], "desconto": v[1], "imposto": v[2], "total": v[4], "pago": v[5]}
    # o pypdf põe o rótulo depois dos números: "... 69 100 810,73Subtotal:" (o último é o Total Doc.)
    t = re.findall(rf"({_NUM_P})\s*Subtotal:", texto)
    return {"documentos": docs, "nao_lidas": nao_lidas, "total_relatorio": num(t[-1]) if t else None,
            "soma": round(sum(d["total"] for d in docs.values()), 2)}
