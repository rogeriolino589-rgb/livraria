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
