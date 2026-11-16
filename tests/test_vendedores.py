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


def test_vendedor_sem_whatsapp_recebe_so_a_tarefa(tmp_path, loja):
    arq = tmp_path / "v.json"
    arq.write_text(json.dumps({"_ajuda": "x", "+258 86 504 8400": {"nome": "Damião Sebastião Cau", "whatsapp": ""},
                               "+258 84 468 9369": {"nome": "", "whatsapp": ""}}))
    vendedores = carregar(arq)
    assert list(vendedores) == ["+258 86 504 8400"]  # linha sem nome é ignorada
    enviados = []
    r = Avisos(lambda n, t: enviados.append(n), vendedores).avisar(loja, IGREJA, "Cliente pede atendimento", "x")
    assert enviados == [] and r["enviado"] is False
    assert loja.listar_tarefas("Damião Sebastião Cau", True)


def test_exemplo_tem_os_vendedores_da_cpad():
    from pathlib import Path

    ex = carregar(Path(__file__).resolve().parent.parent / "config" / "vendedores.exemplo.json")
    assert ex["+258 86 504 8400"]["nome"] == "Damião Sebastião Cau"
    assert ex["+258 84 508 2787"]["nome"] == "Sérgio Paulo Fernando"
    assert ex["+258 87 712 7070"]["nome"] == "Priscila Vilanculos"
    assert "+258 84 468 9369" not in ex  # retalho ainda sem vendedor


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


def test_outros_paises_vao_para_a_linha_internacional():
    import os
    import subprocess
    import sys

    env = {**os.environ, "LIVRARIA_PAIS": "za"}
    saida = subprocess.run([sys.executable, "-c", "from livraria_agentes.vendedores import linha_do_tipo; "
                            "print(linha_do_tipo('Igreja'), linha_do_tipo(None))"],
                           env=env, capture_output=True, text=True, check=True).stdout
    assert saida.split() == ["+258", "87", "712", "7070", "+258", "87", "712", "7070"]


def test_exemplo_usa_as_linhas_corporativas():
    from pathlib import Path

    ex = carregar(Path(__file__).resolve().parent.parent / "config" / "vendedores.exemplo.json")
    assert ex["+258 86 504 8400"]["whatsapp"] == "258865048400"
    assert ex["+258 84 508 2787"]["whatsapp"] == "258845082787"


def test_robo_na_mesma_linha_nao_manda_mensagem_a_si_proprio(loja, monkeypatch):
    monkeypatch.setenv("WHATSAPP_NUMERO_ROBO", "+258 86 504 8400")
    enviados = []
    vendedores = {"+258 86 504 8400": {"nome": "Damião Sebastião Cau", "whatsapp": "258865048400"}}
    r = Avisos(lambda n, t: enviados.append(n), vendedores).avisar(loja, IGREJA, "Pedido novo PED-1", "x")
    assert enviados == [] and "mesma linha" in r["aviso"]
    assert loja.listar_tarefas("Damião Sebastião Cau", True)  # a tarefa fica


def test_por_padrao_o_robo_esta_nas_linhas_corporativas(loja, monkeypatch):
    """Opção 1: o robô atende pelas linhas corporativas; o vendedor vê a conversa na app e recebe a tarefa."""
    from livraria_agentes.vendedores import numeros_do_robo

    monkeypatch.delenv("WHATSAPP_NUMERO_ROBO", raising=False)
    assert {"258865048400", "258845082787", "258844689369", "258877127070"} <= numeros_do_robo()
    enviados = []
    vendedores = carregar()
    r = Avisos(lambda n, t: enviados.append(n), vendedores).avisar(loja, IGREJA, "Cliente pede atendimento", "x")
    assert enviados == [] and r["vendedor"] == "Damião Sebastião Cau"
    assert loja.listar_tarefas("Damião Sebastião Cau", True)
