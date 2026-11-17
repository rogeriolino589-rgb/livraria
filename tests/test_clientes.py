"""Importação da lista de clientes da CPAD e uso no atendimento e no assistente interno."""

from __future__ import annotations

import base64
import gzip
import json

import pytest

from livraria_agentes.importar_clientes import importar, numeros_whatsapp
from livraria_agentes.interno.base import Base
from livraria_agentes.interno.ferramentas import Contexto, executar
from livraria_agentes.loja import Loja
from livraria_agentes.motor import Motor
from test_agentes import AGORA, ClaudeFalso, _msg, _texto

CLIENTES = [
    [1, "IGREJA CRISTO CENTRO", "IGREJA", "", "", "Bairro Central", ""],
    [2, "Igreja Metodista Unida em Moçambique", "IGREJA", "847279956", "Matola", "Matola", ""],
    [3, "José Mabunda", "PASTOR", "84 123 4567", "MAPUTO", "Malhangalene", "Novembro"],
    [4, "Livraria Fé Viva", "REVENDEDOR", "847000001/827000002", "Beira", "Ponta Gêa", ""],
    [5, "Ana Macuácua", "CLIENTE VIP", "258840000001", "Maputo", "Sommerschield", "Novembro"],
]


def _pagina(tmp_path):
    bloco = base64.b64encode(gzip.compress(json.dumps(CLIENTES).encode())).decode()
    caminho = tmp_path / "erp.html"
    caminho.write_text(f'<script id="seed9" type="text/plain">{bloco}</script>', encoding="utf-8")
    return caminho


@pytest.fixture
def loja(tmp_path):
    return Loja(tmp_path / "loja.json", relogio=lambda: AGORA)


def test_numeros_de_mocambique_viram_whatsapp():
    assert numeros_whatsapp("84 727 9956") == ["258847279956"]
    assert numeros_whatsapp("+258 84 727 9956") == ["258847279956"]
    assert numeros_whatsapp("847000001/827000002") == ["258847000001", "258827000002"]
    assert numeros_whatsapp("847000001827000002") == ["258847000001", "258827000002"]
    assert numeros_whatsapp("21 123 45") == [] and numeros_whatsapp("") == []


def test_importa_clientes_sem_apagar_nome_da_conversa(loja, tmp_path):
    r = importar(loja, _pagina(tmp_path))
    assert r["clientes"] == 5 and r["numeros_whatsapp"] == 5 and r["sem_numero_valido"] == 1
    assert r["por_tipo"]["Igreja"] == 2 and r["com_mes_de_aniversario"] == 2
    assert loja.ficha_cliente("258841234567") == {"nome": "José Mabunda", "tipo": "Pastor", "cidade": "Maputo"}
    # o número já existia nos dados de exemplo: mantém o nome que tinha e ganha o tipo e a cidade
    assert loja.ficha_cliente("258840000001")["nome"] == "Ana Macuácua"
    assert loja.ficha_cliente("258827000002")["tipo"] == "Revendedor"


def test_agente_sabe_que_e_um_pastor(loja, tmp_path):
    importar(loja, _pagina(tmp_path))
    falso = ClaudeFalso([_msg(_texto("Paz do Senhor, pastor José! Em que posso ajudar?"))])
    Motor(loja, tmp_path / "c", cliente=falso).responder("258841234567", "Paz do Senhor")
    contexto = falso.chamadas[0][1]["content"]
    assert "José Mabunda" in contexto and "Pastor" in contexto and "Maputo" in contexto


def test_equipa_procura_clientes_e_aniversariantes(loja, tmp_path):
    importar(loja, _pagina(tmp_path))
    ctx = Contexto(loja, Base(tmp_path / "i.db"), None, tmp_path, tmp_path)
    r = json.loads(executar(ctx, "clientes_buscar", {"consulta": "igreja", "tipo": None, "cidade": "matola"}))
    assert r["encontrados"] == 1 and r["clientes"][0]["nome"].startswith("Igreja Metodista")
    assert json.loads(executar(ctx, "clientes_buscar", {"consulta": "", "tipo": "pastor", "cidade": None}))[
        "encontrados"] == 1
    aniv = json.loads(executar(ctx, "clientes_aniversariantes", {"mes": "Novembro"}))
    assert aniv["total"] == 2
    assert json.loads(executar(ctx, "clientes_resumo", {}))["por_tipo"]["Igreja"] == 2
