"""Testes da operação da loja: tarefas da equipa, pagamentos, financeiro, oração e rotinas das 7h30/18h."""

from __future__ import annotations

import json

import pytest

from livraria_agentes.interno import rotinas
from livraria_agentes.interno.base import Base, ErroDados
from livraria_agentes.interno.ferramentas import Contexto, executar
from livraria_agentes.loja import ErroLoja, Loja
from livraria_agentes.motor import Motor
from test_agentes import AGORA, CLIENTE, ClaudeFalso, _ferramenta, _msg, _texto


@pytest.fixture
def loja(tmp_path):
    return Loja(tmp_path / "loja.json", relogio=lambda: AGORA)


@pytest.fixture
def ctx(tmp_path, loja):
    return Contexto(loja, Base(tmp_path / "interno.db"), None, tmp_path / "entrada", tmp_path / "exportacoes")


def test_pedido_gera_tarefa_e_pagamento_vai_ao_financeiro(ctx, loja):
    loja.registrar_cliente(CLIENTE, "Carla")
    pedido = loja.criar_pedido(CLIENTE, [{"livro_id": "L009", "quantidade": 2}], "retirada")
    assert any(pedido["id"] in t["descricao"] for t in loja.listar_tarefas(None, True))

    with pytest.raises(ErroDados, match="confirme"):
        executar(ctx, "pedido_confirmar_pagamento", {"pedido_id": pedido["id"], "forma_pagamento": "mpesa",
                                                     "referencia": None, "confirmado_pela_equipe": False})
    r = json.loads(executar(ctx, "pedido_confirmar_pagamento", {
        "pedido_id": pedido["id"], "forma_pagamento": "mpesa", "referencia": "MP123", "confirmado_pela_equipe": True}))
    assert r["pedido"]["status"] == "pago"
    fin = ctx.base.resumo_financeiro("2026-11-16", "2026-11-16")
    assert fin["entradas"] == 900.0 and fin["por_forma_pagamento"][0]["forma"] == "mpesa"
    assert any("embalar" in t["descricao"] for t in loja.listar_tarefas(None, True))

    with pytest.raises(ErroLoja):
        loja.atualizar_estado_pedido(pedido["id"], "pago")
    assert loja.atualizar_estado_pedido(pedido["id"], "entregue")["status"] == "entregue"


def test_tarefas_da_equipa(ctx, loja):
    t = json.loads(executar(ctx, "tarefa_criar", {"descricao": "Repor a montra das Bíblias",
                                                  "responsavel": "Maria", "prazo": "2026-11-16"}))
    assert [x["id"] for x in json.loads(executar(ctx, "tarefas_listar", {"responsavel": "maria",
                                                                         "so_pendentes": True}))] == [t["id"]]
    executar(ctx, "tarefa_concluir", {"tarefa_id": t["id"]})
    assert loja.listar_tarefas("Maria", True) == []


def test_financeiro_entradas_saidas_e_saldo(ctx):
    for tipo, valor, categoria in (("entrada", 12500, "vendas loja"), ("saida", 3000, "fornecedores"),
                                   ("saida", 500, "transporte")):
        executar(ctx, "financeiro_registrar", {"data": "2026-11-16", "tipo": tipo, "valor": valor,
                                               "categoria": categoria, "descricao": "x", "forma_pagamento": "numerario",
                                               "referencia": None, "confirmado_pela_equipe": True})
    r = json.loads(executar(ctx, "financeiro_resumo", {"inicio": "2026-11-16", "fim": "2026-11-16"}))
    assert (r["entradas"], r["saidas"], r["saldo"]) == (12500.0, 3500.0, 9000.0)
    with pytest.raises(ErroDados):
        ctx.base.registrar_movimento({"data": "2026-11-16", "tipo": "saida", "valor": -5, "categoria": "x"})


def test_pedido_de_oracao_e_contacto_novo(loja, tmp_path):
    falso = ClaudeFalso([
        _msg(_ferramenta(1, "registrar_pedido_oracao", {"pedido": "Orem pela saúde da minha mãe"}),
             stop="tool_use"),
        _msg(_texto("Amém, irmã. A nossa equipa vai orar pela sua mãe. 🙏")),
    ])
    motor = Motor(loja, tmp_path / "c", cliente=falso)
    r = motor.responder(CLIENTE, "Paz do Senhor, podem orar pela minha mãe? Está doente.")
    assert r.textos == ["Amém, irmã. A nossa equipa vai orar pela sua mãe. 🙏"]
    resumo = loja.resumo_operacao(1)
    assert resumo["contactos_novos"] == 1
    assert resumo["pedidos_de_oracao"][0]["pedido"] == "Orem pela saúde da minha mãe"


class AssistenteFalso:
    def __init__(self):
        self.pedidos = []
        self.estados = {}

    def responder(self, conversa, texto, pessoa):
        self.pedidos.append((conversa, texto))
        return ["Paz do Senhor! Resumo do dia. Deus abençoe!"]

    def carregar(self, conversa):
        return self.estados.setdefault(conversa, {"conversa": conversa})

    def salvar(self, estado):
        self.estados[estado["conversa"]] = estado


class CanalFalso:
    def __init__(self):
        self.enviados = []

    def enviar(self, telefone, texto):
        self.enviados.append((telefone, texto))

    def enviar_modelo(self, *args):
        raise AssertionError("não devia precisar de modelo")


def test_rotina_manha_manda_tarefas_a_cada_pessoa(loja, monkeypatch):
    monkeypatch.setenv("EQUIPE_WHATSAPP", "258840000010:Rogério,258840000011:Maria Tembe,258840000012:João")
    monkeypatch.delenv("DONO_WHATSAPP", raising=False)
    loja.criar_tarefa("Repor a montra", "Maria Tembe", None)
    loja.criar_tarefa("Responder às mensagens do Facebook", "João", None)
    loja.criar_tarefa("Contar o stock de revistas", None, None)
    assistente, canal = AssistenteFalso(), CanalFalso()
    r = rotinas.rodar("manha", loja, assistente, canal)
    assert "7h30" in assistente.pedidos[0][1] and "segunda" in assistente.pedidos[0][1]
    enviados = dict(canal.enviados)
    assert enviados["258840000010"].startswith("Paz do Senhor! Resumo do dia.")  # o responsável recebe o resumo
    assert "• Repor a montra" in enviados["258840000011"] and "Paz do Senhor, Maria!" in enviados["258840000011"]
    assert "• Responder às mensagens do Facebook" in enviados["258840000012"]
    assert "1 tarefa(s) da loja ainda sem responsável" in enviados["258840000012"]
    assert set(r["envios"]) == {"258840000010", "258840000011", "258840000012"}


def test_rotina_noite_vai_para_o_dono(loja, monkeypatch):
    monkeypatch.setenv("EQUIPE_WHATSAPP", "258840000011:Maria")
    monkeypatch.setenv("DONO_WHATSAPP", "+258 84 000 0010")
    assistente, canal = AssistenteFalso(), CanalFalso()
    rotinas.rodar("noite", loja, assistente, canal)
    assert "18h" in assistente.pedidos[0][1] and "Pedidos de oração" in assistente.pedidos[0][1]
    assert [t for t, _ in canal.enviados] == ["258840000010"]
    assert assistente.estados["whatsapp-258840000010"]["resumos_pendentes"]
