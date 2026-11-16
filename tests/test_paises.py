"""Perfis por país: Moçambique (em uso) e Eswatini, África do Sul e RD Congo (rascunhos)."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from livraria_agentes.pais import PASTA_PAISES, carregar
from livraria_agentes.textos import TEXTOS

CODIGOS = ["mz", "sz", "za", "cd"]


@pytest.mark.parametrize("codigo", CODIGOS)
def test_todos_os_perfis_carregam(codigo):
    pais = carregar(codigo)
    assert pais.tz and pais.lingua_clientes in TEXTOS and pais.formas_pagamento


def test_dinheiro_no_formato_de_cada_pais():
    assert carregar("mz").dinheiro(1250, True) == "1.250,00 MT"
    assert carregar("za").dinheiro(1250, True) == "R 1 250.00"
    assert carregar("sz").dinheiro(1250, True) == "E 1 250.00"
    assert carregar("cd").dinheiro(1250, True) == "$ 1 250,00"


def test_numeros_de_telefone_por_pais():
    assert carregar("mz").numeros_whatsapp("84 727 9956") == ["258847279956"]
    assert carregar("za").numeros_whatsapp("082 123 4567") == ["27821234567"]
    assert carregar("za").numeros_whatsapp("011 123 4567") == []  # fixo de Joanesburgo, sem WhatsApp
    assert carregar("sz").numeros_whatsapp("7612 3456") == ["26876123456"]
    assert carregar("cd").numeros_whatsapp("+243 81 234 5678") == ["243812345678"]
    assert carregar("cd").numeros_whatsapp("0812345678 / 0991234567") == ["243812345678", "243991234567"]


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
