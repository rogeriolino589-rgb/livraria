"""Planilha de análise de vendas a partir das exportações do Eticadata (ERP19 e ERP22).

    python -m livraria_agentes.interno.relatorio_vendas PASTA [saida.xlsx]

A PASTA tem os .xls exportados da "Análise de Vendas", reconhecidos pelo agrupamento que vem no cabeçalho:
  * "Documento, Artigo resumido a Vendedor"           -> vendedor e artigos de cada documento
  * "Documento"                                       -> data de cada documento
  * "Vendedor, Zona resumido a Tipo de Entidade"      -> tipo de cliente (varejo/atacado) e província
O sistema (ERP19 ou ERP22) vem do período do cabeçalho. Cada relatório é conferido com o seu "Total" e os
documentos são cruzados pelo tipo e número (ex.: V/DIN 2025-001234).
"""

from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

from .analise_vendas import (TIPOS_VENDA, _linhas_xls, canal, ler_datas_linhas, ler_linhas, ler_zonas_linhas,
                             segmento)
from .mapas_eticadata import configuracao


def _cabecalho(caminho: Path) -> tuple[str, str]:
    agrupamento, periodo = "", ""
    for i, linha in enumerate(_linhas_xls(caminho)):
        t = " ".join(str(x) for x in linha if str(x).strip())
        if t.startswith("Período:"):
            periodo = t
        elif t and not agrupamento and i > 3 and "Análise de Vendas" not in t:
            agrupamento = t
        if i > 12:
            break
    m = re.search(r"Período:\s*(\d{2})/(\d{2})/(\d{4})", periodo)
    erp = "ERP19" if m and m.group(3) < "2022" or (m and m.group(3) == "2022" and m.group(2) < "08") else "ERP22"
    return agrupamento, erp


def carregar(pasta: Path) -> dict:
    dados = {"vendedor": {}, "datas": {}, "zonas": {}, "avisos": []}
    for arq in sorted(Path(pasta).glob("*.xls")):
        agrup, erp = _cabecalho(arq)
        linhas = list(_linhas_xls(arq))
        if agrup.startswith("Documento, Artigo"):
            r, chave = ler_linhas(linhas), "vendedor"
        elif agrup.startswith("Documento"):
            r, chave = ler_datas_linhas(linhas), "datas"
        elif "Tipo de Entidade" in agrup and agrup.startswith("Vendedor, Zona"):
            r, chave = ler_zonas_linhas(linhas), "zonas"
        else:
            dados["avisos"].append(f"{arq.name}: agrupamento não usado ({agrup})")
            continue
        if not r["confere"]:
            dados["avisos"].append(f"{arq.name}: a soma {r['soma']} não bate com o total {r['total_relatorio']}")
        dados[chave][erp] = r
    return dados


def gerar(pasta: Path, saida: Path) -> dict:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter as L

    dados = carregar(pasta)
    nomes = configuracao().get("vendedores", {})
    nome = lambda c, erp="": (nomes.get(c) or ("Sem vendedor (N/D)" if c == "N/D" else c)) + (
        " (INATIVO)" if c == "3" and erp == "ERP22" else "")
    datas = {}
    for r in dados["datas"].values():
        datas.update(r["datas"])

    MT, PC = '#,##0.00 "MT"', "0.0%"
    az, ou = PatternFill("solid", fgColor="0B1F3A"), PatternFill("solid", fgColor="F3E9CF")
    wb = Workbook()
    primeira = [True]

    def folha(titulo, cab, larg):
        ws = wb.active if primeira[0] else wb.create_sheet()
        primeira[0] = False
        ws.title = titulo
        for i, t in enumerate(cab, 1):
            c = ws.cell(1, i, t)
            c.font, c.fill = Font(bold=True, color="FFFFFF"), az
            c.alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")
        ws.row_dimensions[1].height = 34
        ws.freeze_panes = "A2"
        for i, w in enumerate(larg, 1):
            ws.column_dimensions[L(i)].width = w
        return ws

    def fmt(ws, r, mt="", pc=""):
        for c in mt:
            ws[f"{c}{r}"].number_format = MT
        for c in pc:
            ws[f"{c}{r}"].number_format = PC

    def destacar(ws, r):
        for c in range(1, ws.max_column + 1):
            ws.cell(r, c).font, ws.cell(r, c).fill = Font(bold=True), ou

    def filtro(ws):
        ws.auto_filter.ref = f"A1:{L(ws.max_column)}{ws.max_row}"

    # documentos de venda com vendedor e data (os que só existem no relatório de datas ficam "por identificar")
    vendas = []
    for erp, r in dados["vendedor"].items():
        vistos = set()
        for d in r["documentos"]:
            vistos.add((d["tipo"], d["numero"]))
            vendas.append({**d, "erp": erp, "data": datas.get((d["tipo"], d["numero"])), "nome": nome(d["vendedor"], erp)})
        for erp_d, rd in dados["datas"].items():
            if erp_d != erp:
                continue
            for (tipo, numero), dt in rd["datas"].items():
                if (tipo, numero) not in vistos:
                    vendas.append({"tipo": tipo, "numero": numero, "ano": numero[:4], "vendedor": "?",
                                   "nome": "Vendedor por identificar", "liquido": rd["valores"][(tipo, numero)], "desconto": 0.0,
                                   "erp": erp, "data": dt, "por_identificar": True})
                    dados["avisos"].append(f"{erp}: {tipo} {numero} ({dt}) está no relatório de datas mas não no "
                                           "de vendedores (exportado antes)")

    # 1. Varejo x Atacado
    ws = folha("Varejo × Atacado", ["Sistema", "Vendedor", "Varejo (MT)", "Atacado (MT)", "Sem tipo N/D (MT)",
                                     "Total (MT)", "% Varejo", "% Atacado", "% Sem tipo"], [12, 36, 18, 18, 16, 18, 10, 10, 10])
    va = collections.defaultdict(collections.Counter)
    for erp, z in dados["zonas"].items():
        for x in z["registos"]:
            for k in ((erp, nome(x["vendedor"], erp)), (erp, "TOTAL " + erp), ("2016–hoje", nome(x["vendedor"])),
                      ("2016–hoje", "TOTAL GERAL")):
                va[k][canal(x["tipo"])] += x["liquido"]
    ordem = ["ERP19", "ERP22", "2016–hoje"]
    for k in sorted(va, key=lambda k: (ordem.index(k[0]), k[1].startswith("TOTAL"), -sum(va[k].values()))):
        r = ws.max_row + 1
        c = va[k]
        ws.append([k[0], k[1], round(c["Varejo"], 2), round(c["Atacado"], 2), round(c["Sem tipo (N/D)"], 2),
                   f"=C{r}+D{r}+E{r}", f"=IF(F{r}=0,0,C{r}/F{r})", f"=IF(F{r}=0,0,D{r}/F{r})", f"=IF(F{r}=0,0,E{r}/F{r})"])
        fmt(ws, r, "CDEF", "GHI")
        if k[1].startswith("TOTAL"):
            destacar(ws, r)
    filtro(ws)
    ws.cell(ws.max_row + 2, 1, "Varejo = Cliente, Cliente VIP, Pastor, Missionários. Atacado = Livrarias, Livraria Cristã, "
            "Igreja, Igreja EBD, Igreja EBD/Livraria, Revendedor, Pastor Revendedor, Empresas/Instituições.")

    # 2. Tipo de entidade
    ws = folha("Tipo de entidade", ["Sistema", "Tipo de entidade", "Canal", "Segmento", "Quantidade",
                                     "Valor líquido (MT)", "% do sistema"], [10, 28, 16, 44, 12, 18, 11])
    for erp, z in dados["zonas"].items():
        c = collections.defaultdict(lambda: [0.0, 0.0])
        for x in z["registos"]:
            c[x["tipo"]][0] += x["quantidade"]
            c[x["tipo"]][1] += x["liquido"]
        for t, (q, v) in sorted(c.items(), key=lambda i: -i[1][1]):
            ws.append([erp, t, canal(t), segmento(t), round(q), round(v, 2), v / z["soma"] if z["soma"] else 0])
            fmt(ws, ws.max_row, "F", "G")
    filtro(ws)

    # 3. Vendedor x Zona
    ws = folha("Vendedor × Zona", ["Sistema", "Vendedor", "Província / zona", "Varejo (MT)", "Atacado (MT)",
                                    "Sem tipo (MT)", "Total (MT)", "% Atacado"], [10, 36, 16, 16, 16, 14, 16, 10])
    vz = collections.defaultdict(collections.Counter)
    for erp, z in dados["zonas"].items():
        for x in z["registos"]:
            vz[(erp, nome(x["vendedor"], erp), x["zona"])][canal(x["tipo"])] += x["liquido"]
    for k, v in sorted(vz.items(), key=lambda i: (i[0][0], i[0][1], -sum(i[1].values()))):
        r = ws.max_row + 1
        ws.append([*k, round(v["Varejo"], 2), round(v["Atacado"], 2), round(v["Sem tipo (N/D)"], 2),
                   f"=D{r}+E{r}+F{r}", f"=IF(G{r}=0,0,E{r}/G{r})"])
        fmt(ws, r, "DEFG", "H")
    filtro(ws)

    # 4. Artigos e 5. Artigos por vendedor
    art = collections.defaultdict(lambda: {"n": "", "q": 0.0, "v": 0.0, "d": set(), "anos": set()})
    av = collections.defaultdict(lambda: {"n": "", "q": 0.0, "v": 0.0})
    tv = collections.Counter()
    for erp, r in dados["vendedor"].items():
        for i in r["itens"]:
            a = art[i["artigo"]]
            a["n"], a["q"], a["v"] = i["nome_artigo"], a["q"] + i["quantidade"], a["v"] + i["liquido"]
            a["d"].add((erp, i["tipo"], i["numero"]))
            a["anos"].add(int(i["ano"]))
            k = (nome(i["vendedor"]), i["artigo"])
            av[k]["n"], av[k]["q"], av[k]["v"] = i["nome_artigo"], av[k]["q"] + i["quantidade"], av[k]["v"] + i["liquido"]
            tv[k[0]] += i["liquido"]
    ws = folha("Artigos (total)", ["Código", "Artigo", "Quantidade", "Valor líquido (MT)", "Nº documentos",
                                    "Preço médio (MT)", "Primeiro ano", "Último ano"], [12, 52, 12, 18, 12, 14, 10, 10])
    for k, a in sorted(art.items(), key=lambda i: -i[1]["v"]):
        r = ws.max_row + 1
        ws.append([k, a["n"], round(a["q"]), round(a["v"], 2), len(a["d"]), f"=IF(C{r}=0,0,D{r}/C{r})",
                   min(a["anos"]), max(a["anos"])])
        fmt(ws, r, "DF")
    filtro(ws)
    ws = folha("Artigos por vendedor", ["Vendedor", "Código", "Artigo", "Quantidade", "Valor líquido (MT)",
                                         "% das vendas do vendedor"], [36, 12, 52, 11, 18, 12])
    for (v, k), a in sorted(av.items(), key=lambda i: (i[0][0], -i[1]["v"])):
        if a["q"] or abs(a["v"]) >= 0.005:
            ws.append([v, k, a["n"], round(a["q"]), round(a["v"], 2), a["v"] / tv[v] if tv[v] else 0])
            fmt(ws, ws.max_row, "E", "F")
    filtro(ws)

    # 6-9. Vendedor por dia, semana do mês, mês, ano
    per = {p: collections.defaultdict(lambda: [0, 0.0]) for p in ("dia", "mes", "ano")}
    for d in vendas:
        if d["tipo"] not in TIPOS_VENDA:
            continue
        chaves = [("ano", d["ano"])]
        if d["data"]:
            chaves += [("dia", d["data"]), ("mes", d["data"][:7])]
        for p, t in chaves:
            g = per[p][(t, d["erp"], d["nome"])]
            g[0] += 1
            g[1] += d["liquido"]
    for titulo, p, rot in (("Vendedor por dia", "dia", "Data"), ("Vendedor por mês", "mes", "Mês"),
                           ("Vendedor por ano", "ano", "Ano")):
        ws = folha(titulo, [rot, "Sistema", "Vendedor", "Nº documentos de venda", "Vendas (MT)", "Ticket médio (MT)"],
                   [12, 10, 36, 14, 18, 16])
        for (t, erp, v), (n, val) in sorted(per[p].items()):
            if not n and not val:
                continue
            r = ws.max_row + 1
            ws.append([t, erp, v, n, round(val, 2), f"=IF(D{r}=0,0,E{r}/D{r})"])
            fmt(ws, r, "EF")
        filtro(ws)

    ws = folha("Notas", ["Notas"], [160])
    ws.append(["Fontes: Análise de Vendas do Eticadata. Cada relatório foi conferido com o seu «Total»; os documentos "
               "foram cruzados pelo tipo e número com o relatório por Documento (data)."])
    ws.append(["Vendas = V/DIN, FACT e TAL. DEVOL e N/CRE (devoluções e notas de crédito) não contam como documentos "
               "de venda."])
    ws.append(["Varejo/atacado por dia, mês e ano ainda não: falta um relatório que ligue cada documento ao tipo de "
               "entidade («Tipo de Entidade, Documento»)."])
    ws.append(["Valores sem IVA e com as faturas (FACT). Por isso diferem do Diário de Vendas do caixa (só V/DIN, com IVA): "
               "ex. 02/11/2026 = 66.730,87 em V/DIN + 4,13 de IVA = 66.735,00 do caixa, mais 18.480,00 em faturas."])
    for a in dados["avisos"]:
        ws.append(["Aviso: " + a])
    Path(saida).parent.mkdir(parents=True, exist_ok=True)
    wb.save(saida)
    return {"arquivo": str(saida), "folhas": {s: wb[s].max_row - 1 for s in wb.sheetnames}, "avisos": dados["avisos"],
            "documentos_com_data": sum(1 for d in vendas if d["data"]), "documentos": len(vendas)}


if __name__ == "__main__":
    pasta = Path(sys.argv[1])
    saida = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("relatorios/CPAD_Mocambique_analise_vendas.xlsx")
    print(gerar(pasta, saida))
