"""Política de descontos para igrejas, instituições, revendedores e livrarias."""

from __future__ import annotations

import pytest

from livraria_agentes.importar_catalogo import converter
from livraria_agentes.loja import Loja, eh_marca_cpad
from test_agentes import AGORA

IGREJA, REVENDEDOR, PASTOR, ANONIMO = "258847000001", "258847000002", "258847000003", "258847000009"


@pytest.fixture
def loja(tmp_path):
    loja = Loja(tmp_path / "loja.json", relogio=lambda: AGORA)
    loja.dados["livros"] = converter([
        ["C1", "9788526308589", "LICAO BIBLICA ADULTOS PROFESSOR", "CPAD - LICOES BIBLICAS", 1000.0, 50],
        ["C2", "7908234018699", "BIBLIA HARPA LETRA GIGANTE", "BIBILIAS", 2000.0, 50],  # CPAD pelo código
        ["O1", "9788573676938", "LIVRO DE OUTRA EDITORA", "LIVROS", 1000.0, 50],
    ])
    for tel, nome, tipo in ((IGREJA, "Igreja Baptista", "Igreja"), (REVENDEDOR, "Livraria Fé", "Revendedor"),
                            (PASTOR, "Pastor José", "Pastor")):
        loja.dados["clientes"][tel] = {"nome": nome, "tipo": tipo}
    return loja


def test_marca_cpad_pela_categoria_ou_pelo_isbn(loja):
    assert [eh_marca_cpad(loja.detalhes_livro(i)) for i in ("C1", "C2", "O1")] == [True, True, False]


def test_igreja_a_partir_de_5000_tem_30_e_15(loja):
    conta = loja.orcamento(IGREJA, [{"livro_id": "C1", "quantidade": 2}, {"livro_id": "C2", "quantidade": 1},
                                    {"livro_id": "O1", "quantidade": 1}], "envio")
    assert conta["subtotal_produtos"] == 5000.0  # chega a 5.000: já tem desconto
    assert [l["desconto_pct"] for l in conta["itens"]] == [30, 30, 15]
    assert conta["desconto"] == 600 + 600 + 150
    assert conta["total"] == 5000 - 1350 + 250  # a taxa de entrega não tem desconto e não conta para o mínimo


def test_abaixo_do_minimo_diz_quanto_falta(loja):
    conta = loja.orcamento(REVENDEDOR, [{"livro_id": "C2", "quantidade": 2}], "retirada")
    assert conta["desconto"] == 0 and conta["total"] == 4000
    assert "faltam 1.000,00 MT" in conta["desconto_info"]


@pytest.mark.parametrize("cliente", [PASTOR, ANONIMO])
def test_quem_nao_e_instituicao_nao_tem_desconto(loja, cliente):
    conta = loja.orcamento(cliente, [{"livro_id": "C2", "quantidade": 5}], "retirada")
    assert conta["desconto"] == 0 and conta["total"] == 10000
    assert "atendente confirma" in conta["desconto_info"]


def test_pedido_guarda_o_desconto_e_o_total(loja):
    pedido = loja.criar_pedido(REVENDEDOR, [{"livro_id": "O1", "quantidade": 6}], "retirada")
    assert (pedido["subtotal_produtos"], pedido["desconto"], pedido["total"]) == (6000.0, 900.0, 5100.0)
    assert loja.detalhes_livro("O1")["estoque"] == 44


def test_politica_ajustavel(loja):
    loja.dados.setdefault("config", {})["desconto_instituicoes"] = {"minimo": 10000.0}
    assert loja.orcamento(IGREJA, [{"livro_id": "C2", "quantidade": 3}], "retirada")["desconto"] == 0
