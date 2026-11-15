"""Testes sem chamar a API: a loja diretamente e o motor com respostas do Claude simuladas."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from anthropic.types.beta import BetaMessage

from livraria_agentes.agentes import AGENTES, SISTEMA
from livraria_agentes.canal import CanalTerminal
from livraria_agentes.ferramentas import FERRAMENTAS, NOMES
from livraria_agentes.lembretes import rodar
from livraria_agentes.loja import FUSO, ErroLoja, Loja
from livraria_agentes.motor import Motor

AGORA = datetime(2026, 11, 16, 10, 0, tzinfo=FUSO)  # segunda-feira
CLIENTE = "258851234567"


@pytest.fixture
def loja(tmp_path):
    return Loja(tmp_path / "loja.json", relogio=lambda: AGORA)


# ------------------------------------------------------------------- loja
def test_busca_por_autor(loja):
    titulos = [l["titulo"] for l in loja.buscar_livros("machado", None, None)]
    assert titulos == ["Dom Casmurro", "Memórias Póstumas de Brás Cubas"]


def test_busca_com_filtro_de_preco(loja):
    assert all(l["preco"] <= 30 for l in loja.buscar_livros("", None, 30))


def test_pedido_baixa_estoque_e_cancelamento_devolve(loja):
    loja.registrar_cliente(CLIENTE, "Carla")
    pedido = loja.criar_pedido(CLIENTE, [{"livro_id": "L001", "quantidade": 2}], "envio")
    assert pedido["total"] == pytest.approx(650 * 2 + 250)
    assert pedido["link_pagamento"].endswith(pedido["id"])
    assert loja.detalhes_livro("L001")["estoque"] == 10
    loja.cancelar_pedido(CLIENTE, pedido["id"])
    assert loja.detalhes_livro("L001")["estoque"] == 12


def test_pedido_exige_nome_e_estoque(loja):
    with pytest.raises(ErroLoja, match="nome"):
        loja.criar_pedido(CLIENTE, [{"livro_id": "L001", "quantidade": 1}], "retirada")
    loja.registrar_cliente(CLIENTE, "Carla")
    with pytest.raises(ErroLoja, match="estoque"):
        loja.criar_pedido(CLIENTE, [{"livro_id": "L012", "quantidade": 1}], "retirada")


def test_cliente_nao_ve_pedido_de_outro(loja):
    with pytest.raises(ErroLoja):
        loja.gerar_link_pagamento(CLIENTE, "PED-DEMO01")  # é da Ana
    assert loja.consultar_pedidos(CLIENTE) == []


def test_pagamento_informado_fica_em_verificacao(loja):
    r = loja.informar_pagamento("258840000001", "PED-DEMO01", "M-Pesa às 9h")
    assert r["status"] == "pagamento_em_verificacao"


def test_agendamento_respeita_vagas_e_horario(loja):
    livres = loja.horarios_disponiveis("2026-11-16")["livres"]
    assert livres[0] == "11:00"  # 9h e 10h já passaram
    assert loja.horarios_disponiveis("2026-11-22")["livres"] == []  # domingo
    loja.agendar(CLIENTE, "retirada", "2026-11-17T14:00", None)
    loja.agendar("258840000001", "retirada", "2026-11-17T14:00", None)
    with pytest.raises(ErroLoja, match="lotado"):
        loja.agendar("258840000002", "retirada", "2026-11-17T14:00", None)
    with pytest.raises(ErroLoja, match="Fora do horário"):
        loja.agendar(CLIENTE, "retirada", "2026-11-17T20:00", None)


# -------------------------------------------------------------- prompts
def test_ferramentas_dos_agentes_existem():
    for agente in AGENTES.values():
        assert agente["ferramentas"] <= NOMES
    assert all(f["input_schema"]["additionalProperties"] is False for f in FERRAMENTAS)
    assert "agendamento" in SISTEMA


# ---------------------------------------------------------- motor (fake)
def _msg(*blocos, stop="end_turn"):
    return BetaMessage.model_validate({
        "id": "msg_x", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": list(blocos), "stop_reason": stop, "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1}})


def _texto(t):
    return {"type": "text", "text": t}


def _ferramenta(i, nome, entrada):
    return {"type": "tool_use", "id": f"toolu_{i}", "name": nome, "input": entrada}


class ClaudeFalso:
    """Devolve respostas prontas e guarda o que recebeu."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []
        self.beta = self
        self.messages = self

    def create(self, **kwargs):
        self.chamadas.append(json.loads(json.dumps(kwargs["messages"])))
        assert kwargs["model"] == "claude-opus-5-5"
        assert kwargs["fallbacks"] == "default"
        return self.respostas.pop(0)


def test_motor_venda_e_transferencia_para_agendamento(loja, tmp_path):
    falso = ClaudeFalso([
        _msg(_ferramenta(1, "buscar_livros", {"consulta": "machado", "genero": None, "preco_max": None}),
             stop="tool_use"),
        _msg(_texto("Temos *Dom Casmurro* por 650,00 MT. Quer retirar na loja?")),
        _msg(_ferramenta(2, "transferir_agente", {"agente": "agendamento", "motivo": "Quer marcar retirada"}),
             stop="tool_use"),
        _msg(_ferramenta(3, "horarios_disponiveis", {"data": "2026-11-17"}), stop="tool_use"),
        _msg(_texto("Amanhã tenho 9h, 10h ou 11h. Qual prefere?")),
    ])
    motor = Motor(loja, tmp_path / "conversas", cliente=falso)

    r1 = motor.responder(CLIENTE, "Tem livro do Machado de Assis?")
    assert r1.textos == ["Temos *Dom Casmurro* por 650,00 MT. Quer retirar na loja?"]
    assert r1.agente == "atendimento_vendas"

    r2 = motor.responder(CLIENTE, "Sim, quero marcar a retirada")
    assert r2.agente == "agendamento"
    assert r2.textos == ["Amanhã tenho 9h, 10h ou 11h. Qual prefere?"]

    # 1ª chamada: mensagem do cliente seguida do contexto como mensagem de sistema
    primeira = falso.chamadas[0]
    assert primeira[0] == {"role": "user", "content": "Tem livro do Machado de Assis?"}
    assert primeira[1]["role"] == "system" and "Agente ativo: atendimento_vendas" in primeira[1]["content"]
    # resultado da busca chegou ao modelo
    resultado = falso.chamadas[1][-1]["content"][0]
    assert resultado["type"] == "tool_result" and "Dom Casmurro" in resultado["content"]
    # depois da transferência, uma mensagem de sistema anuncia o novo agente
    apos_transferencia = falso.chamadas[3]
    assert apos_transferencia[-1]["role"] == "system" and "agendamento" in apos_transferencia[-1]["content"]
    # histórico só cresce: cada chamada começa com a anterior inteira
    for antes, depois in zip(falso.chamadas, falso.chamadas[1:]):
        assert depois[:len(antes)] == antes


def test_motor_bloqueia_ferramenta_de_outro_agente(loja, tmp_path):
    falso = ClaudeFalso([
        _msg(_ferramenta(1, "agendar", {"tipo": "retirada", "data_hora": "2026-11-17T10:00", "observacao": None}),
             stop="tool_use"),
        _msg(_texto("Vou te passar para o agendamento.")),
    ])
    motor = Motor(loja, tmp_path / "c", cliente=falso)
    motor.responder(CLIENTE, "marca pra mim amanhã 10h")
    resultado = falso.chamadas[1][-1]["content"][0]
    assert resultado["is_error"] is True and "transferir_agente" in resultado["content"]
    assert loja.listar_agendamentos(CLIENTE) == []


def test_motor_humano_assume(loja, tmp_path):
    falso = ClaudeFalso([
        _msg(_ferramenta(1, "chamar_humano", {"motivo": "Cliente pediu atendente"}), stop="tool_use"),
        _msg(_texto("Certo! Um atendente vai continuar a conversa.")),
    ])
    motor = Motor(loja, tmp_path / "c", cliente=falso)
    assert motor.responder(CLIENTE, "quero falar com uma pessoa").aguardando_humano
    r = motor.responder(CLIENTE, "oi?")
    assert r.aguardando_humano and r.textos == [] and len(falso.chamadas) == 2  # o robô fica quieto
    assert len(loja.dados["fila_humana"]) == 2

    # a equipe responde e devolve o cliente; o agente fica sabendo do que foi conversado
    motor.registrar_resposta_humana(CLIENTE, "Resolvido, seu livro chega amanhã!")
    motor.liberar_humano(CLIENTE)
    falso.respostas.append(_msg(_texto("Posso ajudar em algo mais?")))
    assert motor.responder(CLIENTE, "valeu!").textos == ["Posso ajudar em algo mais?"]
    aviso = falso.chamadas[-1][-1]["content"]
    assert "Cliente: oi?" in aviso and "Equipe: Resolvido" in aviso


def test_lembretes_e_resposta_do_cliente(loja, tmp_path, capsys):
    falso = ClaudeFalso([_msg(_texto("Perfeito, Ana! Aqui está o link de novo."))])
    motor = Motor(loja, tmp_path / "c", cliente=falso)
    assert rodar(loja, motor, CanalTerminal(), "Livraria Teste") == 2
    saida = capsys.readouterr().out
    assert "PED-DEMO01" in saida and "Hábitos Atómicos" in saida
    assert rodar(loja, motor, CanalTerminal(), "Livraria Teste") == 0  # não repete no mesmo dia

    r = motor.responder("258840000001", "Esqueci! Manda o link?")
    assert r.agente == "cobranca"
    aviso = falso.chamadas[0][-1]
    assert aviso["role"] == "system" and "PED-DEMO01" in aviso["content"]
