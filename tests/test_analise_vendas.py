"""Relatório "Análise de Vendas" do Eticadata, no formato real, com valores inventados."""

from livraria_agentes.interno.analise_vendas import ler_linhas, resumo

LINHAS = [
    ["eticadata software lda."], ["Análise de Vendas"], ["Documento, Artigo resumido a  Vendedor"],
    ["Código", "", "Nome", "Qtd.", "Valor", "Desconto", "Valor Líquido"],
    ["Documento: V/DIN - 2025-000001"],
    ["Artigo: 1 - BIBLIA"], ["2", "", "Vendedor A", 1.0, 1000.0, -100.0, 900.0], ["Total Artigo: ", 1.0, 1000.0, -100.0, 900.0],
    ["Artigo: 2 - HARPA"], ["2", "", "Vendedor A", 2.0, 600.0, 0.0, 600.0],
    ["Total Documento: ", 3.0, 1600.0, -100.0, 1500.0],
    ["Documento: V/DIN - 2025-000002"], ["Artigo: 3 - LIVRO"], ["7.0", "Vendedor B", 1.0, 500.0, 0.0, 500.0],
    ["Documento: DEVOL - 2025-000001"], ["Artigo: 3 - LIVRO"], ["7", "Vendedor B", 0.0, -500.0, 0.0, -500.0],
    ["Documento: FACT - 2026-000001"], ["Artigo: 1 - BIBLIA"], ["3", "INATIVO", 10.0, 10000.0, -3000.0, 7000.0],
    ["Total: ", 0.0, 0.0, 0.0, 8500.0],
]


def test_documentos_e_conferencia():
    r = ler_linhas(LINHAS)
    assert r["confere"] and r["soma"] == 8500.0 and len(r["documentos"]) == 4
    d1 = r["documentos"][0]
    assert (d1["tipo"], d1["numero"], d1["vendedor"], d1["liquido"], d1["desconto"]) == ("V/DIN", "2025-000001", "2", 1500.0, -100.0)


def test_resumo_por_ano_e_vendedor():
    linhas = resumo(ler_linhas(LINHAS)["documentos"], {"3": "José Tovela (INATIVO)"})
    chave = {(x["ano"], x["vendedor"]): x for x in linhas}
    assert chave[("2025", "2")]["ticket_medio"] == 1500.0
    b = chave[("2025", "7")]
    assert (b["documentos"], b["vendas"], b["devolucoes"]) == (1, 500.0, -500.0)  # devolução não conta como venda
    assert chave[("2026", "3")]["nome"] == "José Tovela (INATIVO)"


def test_total_que_nao_bate():
    assert not ler_linhas(LINHAS[:-1] + [["Total: ", 1.0]])["confere"]


def test_tipo_de_cliente_e_zona():
    from livraria_agentes.interno.analise_vendas import ler_zonas_linhas, segmento

    linhas = [["Análise de Vendas"], ["Vendedor: 2 - Vendedor A"], ["Zona: 11 - MAPUTO"],
              ["4", "EMPRESAS / INSTITUIÇÕES", 1.0, 900.0, -100.0, 800.0], ["5", "IGREJA", 2.0, 300.0, 0.0, 300.0],
              ["Total Zona: ", 3.0, 1200.0, -100.0, 1100.0], ["Zona: EXT - Extrangeiro"],
              ["N/D", "N/D", 1.0, 50.0, 0.0, 50.0], ["Total: ", 4.0, 1250.0, -100.0, 1150.0]]
    r = ler_zonas_linhas(linhas)
    assert r["confere"] and [(x["vendedor"], x["zona"], x["segmento"]) for x in r["registos"]] == [
        ("2", "Maputo", "Empresas e instituições"), ("2", "Maputo", "Igrejas"), ("2", "Extrangeiro", "Sem tipo (N/D)")]
    # o código 4 era LIVRARIA no ERP19: o segmento vem da descrição, não do código
    assert segmento("LIVRARIA") == "Livrarias e revendedores" and segmento("IGREJA EBD/ LIVRARIA") == "Livrarias e revendedores"
    assert segmento("CLIENTE VIP") == segmento("PASTOR") == segmento("MISSIONARIOS")


def test_varejo_e_atacado():
    from livraria_agentes.interno.analise_vendas import canal

    for d in ("CLIENTE", "CLIENTE VIP", "PASTOR", "MISSIONARIOS"):
        assert canal(d) == "Varejo", d
    for d in ("LIVRARIA", "LIVRARIA CRISTA", "IGREJA", "IGREJA EBD", "IGREJA EBD/ LIVRARIA", "REVENDEDOR",
              "PASTOR REVENDEDOR", "EMPRESAS / INSTITUIÇÕES"):
        assert canal(d) == "Atacado", d
    assert canal("N/D") == "Sem tipo (N/D)"


def test_artigos_e_datas():
    from livraria_agentes.interno.analise_vendas import ler_datas_linhas

    itens = ler_linhas(LINHAS)["itens"]
    assert [(i["numero"], i["artigo"], i["vendedor"], i["liquido"]) for i in itens[:2]] == [
        ("2025-000001", "1", "2", 900.0), ("2025-000001", "2", "2", 600.0)]
    r = ler_datas_linhas([["V/DIN", "2025-000001", "05/11/2025", 3.0, 1600.0, -100.0, 1500.0],
                          ["Total: ", 3.0, 1600.0, -100.0, 1500.0]])
    assert r["confere"] and r["datas"][("V/DIN", "2025-000001")] == "2025-11-05"
