"""Mapas diários do Eticadata (Diário de Vendas e Mapa de Caixa), no formato real, com valores inventados."""

from livraria_agentes.interno.base import Base
from livraria_agentes.interno.classificar_docs import classificar
from livraria_agentes.interno.mapas_eticadata import conferir, ler_diario_vendas, ler_mapa_caixa

DIARIO = (
    "CASA PUBLICADORA EXEMPLO, LDA  Diário de Vendas  Por Tipo de Documento  Secção: SEDE  Período:   De 05/11/2026 "
    "das 00:00 Até 05/11/2026 às 23:59 ;   Moeda:   MT  Data Doc.   Documento   Desc. Meio Pag.   Descontos   "
    "Valor Pago Vend.   Mercadoria   Total Impostos   Total Doc. Acertos   Dif.Arred.  Secção: SEDE  "
    "05/11/2026   V/DIN 2026-000101   7   Ponto 24   1.000,00   0,00   0,00   0,00   1.000,00   1.000,00   0,00 "
    "05/11/2026   V/DIN 2026-000102   2   Dinheiro   500,00   -50,00   0,00   0,00   450,00   450,00   0,00 "
    "05/11/2026   V/DIN 2026-000103   7   Dinheiro / Ponto 24   2.586,21   0,00   413,79   0,00   3.000,00   "
    "3.000,00   0,00  -50,00 Subtotal SEDE:   4.450,00 Quadro Resumo do Impostos SEDE Código   Valor Incidência "
    "Taxa  1   0,00   1.450,00   0,00 3   16,00   2.586,21   413,79 413,79  DiarioVendasTpDoc.Rpt   05/11/2026 "
    # o Eticadata repete o quadro numa 2.ª página; os documentos não podem contar duas vezes
    "05/11/2026   V/DIN 2026-000101   7   Ponto 24   1.000,00   0,00   0,00   0,00   1.000,00   1.000,00   0,00")

CAIXA = (
    "CASA PUBLICADORA EXEMPLO, LDA  Mapa de Caixa  Resumo Data: 05/11/2026 18:00:06  Posto: PV1-1  Abertura de "
    "Caixa Num.: 2026-000251 - 05/11/2026 09:10:00  1.000,00 Dinheiro  Soma:   1.000,00 Movimentos do Dia Vendas + "
    "Cheques-Oferta  1.950,00 Dinheiro 2.500,00 Ponto 24  Soma:   4.450,00 Total (Movimentos do Dia):   4.450,00 "
    "Fecho do Caixa - 05/11/2026 18:00:06 Resumo  Abertura de Caixa   1.000,00 Vendas Anuladas   0,00 Devoluções   "
    "0,00 Vendas   4.450,00 Descontos   50,00 Nº Vendas   3,00 Venda Média   1.483,33  Caixa.rpt")


def test_diario_de_vendas():
    d = ler_diario_vendas(DIARIO)
    assert [x["documento"] for x in d["documentos"]] == ["V/DIN 2026-000101", "V/DIN 2026-000102", "V/DIN 2026-000103"]
    assert d["total"] == 4450.00 and d["descontos"] == -50.00 and d["seccao"] == "SEDE"
    assert d["por_meio_pagamento"] == {"Ponto 24": 1000.0, "Dinheiro": 450.0, "Dinheiro / Ponto 24": 3000.0}
    assert d["por_vendedor"] == {"7": 4000.0, "2": 450.0}
    assert d["impostos"] == [{"codigo": "1", "taxa": 0.0, "incidencia": 1450.0, "imposto": 0.0},
                             {"codigo": "3", "taxa": 16.0, "incidencia": 2586.21, "imposto": 413.79}]


def test_mapa_de_caixa_e_conferencia():
    c = ler_mapa_caixa(CAIXA)
    assert (c["data"], c["posto"], c["abertura_num"], c["fundo_caixa"]) == ("2026-11-05", "PV1-1", "2026-000251", 1000.0)
    assert c["movimentos"] == {"Dinheiro": 1950.0, "Ponto 24": 2500.0}
    assert c["resumo"]["Vendas"] == 4450.0 and c["resumo"]["Nº Vendas"] == 3 and c["resumo"]["Descontos"] == 50.0
    assert conferir(ler_diario_vendas(DIARIO), c) == []


def test_conferencia_acusa_diferenca():
    c = ler_mapa_caixa(CAIXA.replace("Vendas   4.450,00", "Vendas   4.500,00"))
    assert any("Vendas no caixa 4500.00" in a for a in conferir(ler_diario_vendas(DIARIO), c))


def test_importar_para_o_historico(tmp_path):
    base = Base(tmp_path / "b.db")
    r = base.importar_diario_vendas(DIARIO, CAIXA, "DiarioVendas 05.11.pdf")
    assert r["ok"] and r["erp"] == "erp22" and r["documentos"] == 3 and r["total"] == 4450.0
    assert base._q("SELECT SUM(valor) s FROM vendas")[0]["s"] == 4450.0
    assert base.importar_diario_vendas(DIARIO, CAIXA)["aviso"].startswith("Este Diário")


def test_nao_grava_se_nao_bater(tmp_path):
    base = Base(tmp_path / "b.db")
    r = base.importar_diario_vendas(DIARIO, CAIXA.replace("Nº Vendas   3,00", "Nº Vendas   4,00"))
    assert not r["ok"] and base._q("SELECT COUNT(*) n FROM vendas")[0]["n"] == 0


def test_email_resumo_diario_e_relatorio():
    r = classificar("Resumo de vendas diário", "loja@exemplo.mz", ["Caixa 03.11.pdf", "DiarioVendas 03.11.pdf"])
    assert r["tipo"] == "relatorio_vendas" and r["guardar"]


def test_vendedores_pelo_nome(tmp_path):
    r = Base(tmp_path / "b.db").importar_diario_vendas(DIARIO, CAIXA)
    assert r["por_vendedor"] == {"Damião Sebastião Cau (7)": 4000.0, "Guacha (2)": 450.0}
