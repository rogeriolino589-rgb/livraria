"""Importação do catálogo da CPAD (página do ERP, JSON ou planilha) e busca no catálogo real."""

from __future__ import annotations

import base64
import gzip
import json

import pytest
from openpyxl import Workbook

from livraria_agentes.importar_catalogo import importar
from livraria_agentes.loja import ErroLoja, Loja
from test_agentes import AGORA, CLIENTE

PRODUTOS = [
    ["01230", "9788580642254", "BIBLIA RC GRANDE BROCHURA", "CPAD - BIBLIAS", 380.0, 15],
    ["020", "9788578607197", "BIBLIA LEITURA PERFEITA CAPA VERDE", "BIBILIAS", 4320.0, 0],
    ["01627", "", "BIBLIA LT GDE VENEZA PRETA", "", 0.0, 0],
    ["0100", "9788577422166", "E SE DEUS FOR CONTRA NOS", "LIVROS", 1314.0, 2],
    ["0200", "", "LICOES BIBLICAS ADULTOS 4 TRIMESTRE", "CPAD - LICOES BIBLICAS", 250.0, 40],
]


def _pagina(tmp_path, linhas):
    bloco = base64.b64encode(gzip.compress(json.dumps(linhas).encode())).decode()
    caminho = tmp_path / "erp.html"
    caminho.write_text(f'<html><script id="seed8" type="text/plain">{bloco}</script></html>', encoding="utf-8")
    return caminho


@pytest.fixture
def loja(tmp_path):
    return Loja(tmp_path / "loja.json", relogio=lambda: AGORA)


def test_importa_da_pagina_do_erp(loja, tmp_path):
    r = importar(loja, _pagina(tmp_path, PRODUTOS))
    assert r == {"produtos": 5, "com_preco": 4, "com_preco_marca_cpad": 2, "com_preco_e_stock": 3,
                 "por_categoria": {"Bíblias": 2, "Lições Bíblicas (Escola Dominical)": 1, "Livros": 1}}
    assert loja.detalhes_livro("01230")["genero"] == "Bíblias"
    assert loja.dados["pedidos"]  # o resto da loja continua igual


def test_busca_sem_acentos_e_sem_produtos_sem_preco(loja, tmp_path):
    importar(loja, _pagina(tmp_path, PRODUTOS))
    achados = loja.buscar_livros("Quanto custa a Bíblia?", None, None)
    assert [a["id"] for a in achados] == ["01230", "020"]  # com stock primeiro; a sem preço não aparece
    assert len(loja.buscar_livros("biblia", None, None, incluir_sem_preco=True)) == 3
    assert loja.buscar_livros("lições bíblicas", None, None)[0]["id"] == "0200"
    assert loja.buscar_livros("9788577422166", None, None)[0]["id"] == "0100"


def test_produto_sem_preco_nao_e_vendido(loja, tmp_path):
    importar(loja, _pagina(tmp_path, PRODUTOS))
    loja.registrar_cliente(CLIENTE, "Carla")
    with pytest.raises(ErroLoja, match="sem preço"):
        loja.criar_pedido(CLIENTE, [{"livro_id": "01627", "quantidade": 1}], "retirada")
    pedido = loja.criar_pedido(CLIENTE, [{"livro_id": "01230", "quantidade": 2}], "retirada")
    assert pedido["total"] == 760.0


def test_importa_de_planilha(loja, tmp_path):
    wb = Workbook()
    aba = wb.active
    aba.append(["Código", "ISBN", "Designação", "Família", "PVP", "Existência"])
    aba.append(["A1", "978", "HARPA CRISTA GRANDE", "HARPA CRISTA", "650,00", 4])
    wb.save(tmp_path / "produtos.xlsx")
    assert importar(loja, tmp_path / "produtos.xlsx")["com_preco_e_stock"] == 1
    assert loja.detalhes_livro("A1") | {} == {"id": "A1", "isbn": "978", "titulo": "HARPA CRISTA GRANDE", "autor": "",
                                             "genero": "Harpa Cristã", "preco": 650.0, "estoque": 4, "sinopse": "",
                                             "marca": ""}
