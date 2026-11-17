"""Avaliação (evals) da Skill faturas-borderos: casos no formato dos e-mails reais, com dados inventados."""

import pytest

from livraria_agentes.interno.classificar_docs import classificar, extracto_conta_corrente

CASOS = [
    # (assunto, remetente, anexos, texto, tipo esperado, guardar)
    ("Vendas CPAD Moçambique", "loja@exemplo.mz", ["11-Faturamento - Filial Moçambique Novembro 2026.xlsx"],
     "Sirvo-me do presente e-mail, para enviar o resultado das vendas", "relatorio_vendas", True),
    ("Extracto de Conta", "fornecedor@exemplo.com", ["Conta Corrente CPAD Livraria - Moçambique.pdf"],
     "Anexo o extracto conforme solicitado.", "extracto_fornecedor", True),
    ("Fw: PAGAMENTOS ALUGUÉIS", "gerente@exemplo.mz",
     ["Transferencias_Entre_Contas_Do_Mesmo_Banco (7).pdf"], "Envio os borderôs de pagamento das rendas.",
     "bordero_pagamento", True),
    ("Recibo", "editora@exemplo.com", ["SKM_C250i26111316490.pdf"], "Anexo o recibo.", "recibo", True),
    ("FW:Envio de Faturas e Dados Bancários", "info@exemplo.co.mz", ["FT 2026-118.pdf", "NIB.pdf"],
     "encontrar em anexo as faturas e os dados bancários", "fatura_fornecedor", True),
    ("Documento de pagamento", "gerente@exemplo.mz", ["imagem.png"],
     "Olá SUZANA! Obrigado por pagar com o M-Pesa. Valor 1.500,00MT", "comprovativo_carteira", True),
    # Conversa sobre faturas, sem anexo: não é documento para arquivar.
    ("Re: FW:Envio de Faturas e Dados Bancários", "financas@exemplo.co.mz", [],
     "Grato, já encaminhamos a nossa direção. Efetuaremos a liquidação.", "fatura_fornecedor", False),
    # Publicidade que fala em "faturar" não é fatura.
    ("Aula Master Reabertura Formação", "palestra@exemplo.com.br", [],
     "Master de Licitação e faturar acima de 10 mil reais por mês. Clique aqui", "publicidade", False),
    ("Faltam menos de 10 horas para encerrar", "palestra@exemplo.com.br", [],
     "potencial de faturar acima de R$10 mil por mês", "publicidade", False),
    ("Reunião de sexta", "colega@exemplo.mz", [], "Vamos falar do inventário.", "outro", False),
]


@pytest.mark.parametrize("assunto,remetente,anexos,texto,tipo,guardar", CASOS)
def test_classificacao(assunto, remetente, anexos, texto, tipo, guardar):
    r = classificar(assunto, remetente, anexos, texto)
    assert (r["tipo"], r["guardar"]) == (tipo, guardar), r["motivo"]


EXTRACTO = (
    "Conta Corrente CPAD Livraria - Moçambique | de 2026-01-01 até 2026-11-12  Data   TipoDoc   NumDoc   Débito   "
    "Crédito   Saldo  Saldo Inicial   5000.00   6000.00   -1000.00 "
    "2026-02-04   Factura de Cliente   FCC 202600017   3000.00   2000.00 "
    "2026-04-21   Factura de Cliente   FCC 202600102   1500.00   3500.00 "
    "2026-05-06   Recibos   REC 202600060   3500.00   0.00 "
    "2026-08-21   Factura de Cliente   FCC 202600190   700.00   700.00 "
    "2026-10-29   Factura de Cliente   FCC 202600234   1200.50   1900.50 "
    "2026-10-30   Recibos   REC 202600099   500.00   1400.50 "
    "Total   11400.50   10000.00   1400.50  Page 1")


def test_extracto_saldo_e_em_aberto():
    r = extracto_conta_corrente(EXTRACTO)
    assert r["saldo_inicial"] == -1000.00
    assert r["saldo_final"] == 1400.50
    assert [x["natureza"] for x in r["lancamentos"]] == ["debito", "debito", "credito", "debito", "debito", "credito"]
    assert r["avisos"] == []
    # O recibo de 500 paga a fatura mais antiga em aberto (FCC 190 fica com 200 por pagar).
    assert [(x["documento"], x["em_aberto"], x["parcial"]) for x in r["em_aberto"]] == [
        ("FCC 202600190", 200.00, True), ("FCC 202600234", 1200.50, False)]


def test_extracto_saldo_que_nao_bate_gera_aviso():
    texto = EXTRACTO.replace("3500.00   0.00", "3500.00   10.00")
    r = extracto_conta_corrente(texto)
    assert any("REC 202600060" in a for a in r["avisos"])


def test_extracto_virgula_decimal():
    texto = "Saldo Inicial 0,00 0,00 0,00 2026-03-01 Factura FT 20260001 1.234,50 1.234,50"
    r = extracto_conta_corrente(texto)
    assert r["saldo_final"] == 1234.50 and r["em_aberto"][0]["documento"] == "FT 20260001"
