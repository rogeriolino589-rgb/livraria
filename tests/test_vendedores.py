"""Avisos ao vendedor da linha certa quando o robô passa o cliente para uma pessoa ou recebe um pedido."""

from __future__ import annotations

import json

import pytest

from livraria_agentes.loja import Loja
from livraria_agentes.motor import Motor
from livraria_agentes.vendedores import Avisos, carregar, linha_do_tipo
from test_agentes import AGORA, ClaudeFalso, _ferramenta, _msg, _texto

IGREJA, LIVRARIA, PASTOR = "258847000001", "258847000002", "258847000003"
VENDEDORES = {"+258 86 504 8400": {"nome": "Maria", "whatsapp": "258840000101"},
              "+258 84 508 2787": {"nome": "João", "whatsapp": "258840000102"}}


@pytest.fixture
def loja(tmp_path):
    loja = Loja(tmp_path / "loja.json", relogio=lambda: AGORA)
    for tel, nome, tipo in ((IGREJA, "Igreja Baptista da Maxaquene", "Igreja"), (LIVRARIA, "Livraria Fé", "Livraria"),
                            (PASTOR, "Pastor José", "Pastor")):
        loja.dados["clientes"][tel] = {"nome": nome, "tipo": tipo}
    return loja


def test_linha_de_cada_tipo():
    assert linha_do_tipo("Igreja") == "+258 86 504 8400"
    assert linha_do_tipo("Empresa / instituição") == linha_do_tipo("Revendedor") == "+258 84 508 2787"
    assert linha_do_tipo("Pastor") == linha_do_tipo(None) == "+258 84 468 9369"


def test_igreja_pede_atendente_e_a_vendedora_das_igrejas_e_avisada(loja, tmp_path):
    enviados = []
    falso = ClaudeFalso([_msg(_ferramenta(1, "chamar_humano", {"motivo": "Quer 200 Lições Bíblicas com fatura"}),
                              stop="tool_use"),
                         _msg(_texto("Paz do Senhor! A nossa irmã Maria vai continuar o atendimento."))])
    motor = Motor(loja, tmp_path / "c", cliente=falso,
                  avisos=Avisos(lambda n, t: enviados.append((n, t)), VENDEDORES))
    motor.responder(IGREJA, "Precisamos de 200 lições com fatura")
    assert [n for n, _ in enviados] == ["258840000101"]
    texto = enviados[0][1]
    assert "Igreja Baptista da Maxaquene (Igreja)" in texto and "https://wa.me/258847000001" in texto
    assert "200 Lições" in texto
    assert loja.listar_tarefas("Maria", True)[0]["descricao"].startswith("Cliente pede atendimento")


def test_pedido_de_livraria_avisa_o_outro_vendedor(loja, tmp_path):
    enviados = []
    falso = ClaudeFalso([_msg(_ferramenta(1, "criar_pedido", {"itens": [{"livro_id": "L001", "quantidade": 1}],
                                                              "entrega": "retirada"}), stop="tool_use"),
                         _msg(_texto("Pedido criado!"))])
    motor = Motor(loja, tmp_path / "c", cliente=falso,
                  avisos=Avisos(lambda n, t: enviados.append((n, t)), VENDEDORES))
    motor.responder(LIVRARIA, "Quero o Dom Casmurro")
    assert enviados[0][0] == "258840000102" and "Pedido novo PED-" in enviados[0][1]
    assert "650,00 MT" in enviados[0][1]


def test_linha_sem_vendedor_configurado_nao_avisa(loja, tmp_path):
    enviados = []
    avisos = Avisos(lambda n, t: enviados.append(n), VENDEDORES)
    assert avisos.avisar(loja, PASTOR, "Cliente pede atendimento", "x") is None and enviados == []


def test_falha_no_envio_nao_estraga_o_atendimento(loja):
    def falha(n, t):
        raise RuntimeError("sem rede")

    r = Avisos(falha, VENDEDORES).avisar(loja, IGREJA, "Cliente pede atendimento", "x")
    assert r["enviado"] is False and loja.listar_tarefas("Maria", True)  # a tarefa fica registada


def test_configuracao_sem_numero_e_ignorada(tmp_path):
    arq = tmp_path / "v.json"
    arq.write_text(json.dumps({"_ajuda": "x", "+258 86 504 8400": {"nome": "Maria", "whatsapp": ""},
                               "+258 84 508 2787": {"nome": "João", "whatsapp": "258840000102"}}))
    assert list(carregar(arq)) == ["+258 84 508 2787"]


def test_fora_da_janela_de_24h_usa_o_modelo_aprovado(loja):
    modelos = []

    def falha(n, t):
        raise RuntimeError("fora da janela de 24h")

    r = Avisos(falha, VENDEDORES, enviar_modelo=lambda *a: modelos.append(a)).avisar(
        loja, IGREJA, "Pedido novo PED-1", "Total: 9.000,00 MT")
    assert r["enviado"] is True
    numero, modelo, parametros, texto = modelos[0]
    assert (numero, modelo) == ("258840000101", "aviso_vendedor")
    assert parametros == ["Maria", "Pedido novo PED-1", "Igreja Baptista da Maxaquene", "+258847000001"]
    assert texto.startswith("Olá, Maria! Pedido novo PED-1: Igreja Baptista da Maxaquene (+258847000001).")
