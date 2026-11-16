"""Perfis por país: Moçambique (em uso) e Eswatini, África do Sul e RD Congo (rascunhos)."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from livraria_agentes.pais import PASTA_PAISES, carregar
from livraria_agentes.textos import TEXTOS

CODIGOS = ["mz", "sz", "za", "cd", "mu"]


@pytest.mark.parametrize("codigo", CODIGOS)
def test_todos_os_perfis_carregam(codigo):
    pais = carregar(codigo)
    assert pais.tz and pais.lingua_clientes in TEXTOS and pais.formas_pagamento


def test_dinheiro_no_formato_de_cada_pais():
    assert carregar("mz").dinheiro(1250, True) == "1.250,00 MT"
    assert carregar("za").dinheiro(1250, True) == "R 1 250.00"
    assert carregar("sz").dinheiro(1250, True) == "E 1 250.00"
    assert carregar("cd").dinheiro(1250, True) == "$ 1 250,00"
    assert carregar("mu").dinheiro(1250, True) == "Rs 1,250.00"


def test_numeros_de_telefone_por_pais():
    assert carregar("mz").numeros_whatsapp("84 727 9956") == ["258847279956"]
    assert carregar("za").numeros_whatsapp("082 123 4567") == ["27821234567"]
    assert carregar("za").numeros_whatsapp("011 123 4567") == []  # fixo de Joanesburgo, sem WhatsApp
    assert carregar("sz").numeros_whatsapp("7612 3456") == ["26876123456"]
    assert carregar("cd").numeros_whatsapp("+243 81 234 5678") == ["243812345678"]
    assert carregar("cd").numeros_whatsapp("0812345678 / 0991234567") == ["243812345678", "243991234567"]
    assert carregar("mu").numeros_whatsapp("5712 3456") == ["23057123456"]
    assert carregar("mu").numeros_whatsapp("212 3456") == []  # fixo


def test_textos_completos_em_todas_as_linguas():
    for lingua in ("en", "fr"):
        assert set(TEXTOS[lingua]) == set(TEXTOS["pt"])
        assert "{{6}}" in TEXTOS[lingua]["modelo_lembrete_pagamento"]


def test_pais_desconhecido_explica():
    with pytest.raises(SystemExit, match="Disponíveis"):
        carregar("xx")


def _rodar(codigo: str, codigo_python: str) -> str:
    env = {**os.environ, "LIVRARIA_PAIS": codigo}
    env.pop("LOJA_NOME", None)
    return subprocess.run([sys.executable, "-c", codigo_python], env=env, capture_output=True, text=True,
                          check=True, cwd=PASTA_PAISES.parent.parent).stdout


def test_robo_da_africa_do_sul_fala_ingles_e_usa_rand():
    saida = _rodar("za", "from livraria_agentes.agentes import SISTEMA, NOME_LOJA; "
                         "from livraria_agentes.motor import MSG_INSTABILIDADE; "
                         "print(NOME_LOJA); print(SISTEMA); print(MSG_INSTABILIDADE)")
    assert "CPAD South Africa" in saida and "R 1 250.00" in saida and "inglês simples" in saida
    assert "não ofereça nenhum desconto" in saida  # ainda sem política de descontos definida
    assert "Sorry, we had a technical problem" in saida


def test_robo_da_rdc_fala_frances():
    saida = _rodar("cd", "from livraria_agentes.lembretes import MODELOS; from livraria_agentes.loja import FUSO; "
                         "from livraria_agentes.canal import CanalWhatsApp; "
                         "print(MODELOS['pos_venda']); print(FUSO); print(CanalWhatsApp('t', '1').idioma)")
    assert "Bonjour {{1}}" in saida and "Africa/Kinshasa" in saida and saida.strip().endswith("fr")


def test_carteiras_eletronicas_de_cada_pais():
    ids = {c: carregar(c).ids_pagamento for c in CODIGOS}
    assert {"mpesa", "emola", "mkesh"} <= set(ids["mz"])
    assert {"mtn_momo", "emali", "instacash"} <= set(ids["sz"])
    assert {"capitec_pay", "payshap", "qr"} <= set(ids["za"])
    assert {"mpesa", "orange_money", "airtel_money", "afrimoney"} <= set(ids["cd"])
    assert {"mcb_juice", "blink", "myt_money", "maucas_qr"} <= set(ids["mu"])
    assert all("numerario" in i and i[-1] == "outra" for i in ids.values())
    assert "e-Mola (Movitel)" in carregar("mz").descricao_pagamentos()


def test_robo_das_mauricias_e_pagamento_no_pdv():
    saida = _rodar("mu", "from livraria_agentes.agentes import SISTEMA; "
                         "from livraria_agentes.interno.ferramentas import FORMAS_PAGAMENTO; "
                         "print(SISTEMA); print(FORMAS_PAGAMENTO)")
    assert "MCB Juice (MCB)" in saida and "Rs 1,250.00" in saida and "'blink'" in saida


def test_linhas_de_atendimento_por_tipo_de_cliente():
    from livraria_agentes.agentes import SISTEMA

    assert "Igreja: +258 86 504 8400" in SISTEMA
    assert "Empresa / instituição, Livraria, Revendedor, Pastor revendedor: +258 84 508 2787" in SISTEMA
    assert "Cliente VIP, Pastor, Missionário, Cliente, sem cadastro: +258 84 468 9369" in SISTEMA
