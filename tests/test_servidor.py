"""Testes do webhook e do envio pelo WhatsApp, sem rede: a Meta e o Claude são simulados."""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from livraria_agentes.canal import LIMITE_TEXTO, CanalWhatsApp, _partes
from livraria_agentes.lembretes import preencher
from livraria_agentes.loja import Loja
from livraria_agentes.motor import Motor
from livraria_agentes.servidor import criar_app, extrair_texto
from test_agentes import AGORA, ClaudeFalso, _msg, _texto

SEGREDO = "segredo-do-app"
VERIFICA = "minha-senha"


class MetaFalsa:
    """Faz o papel da graph.facebook.com e guarda o que foi enviado."""

    def __init__(self):
        self.envios = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer TOKEN"
        assert request.url.path == "/v23.0/123/messages"
        self.envios.append(json.loads(request.content))
        return httpx.Response(200, json={"messages": [{"id": "wamid.x"}]})


@pytest.fixture
def meta():
    return MetaFalsa()


@pytest.fixture
def canal(meta):
    return CanalWhatsApp("TOKEN", "123", cliente_http=httpx.Client(transport=httpx.MockTransport(meta)))


def _webhook(*mensagens):
    return {"object": "whatsapp_business_account", "entry": [{"id": "WABA", "changes": [{"field": "messages",
            "value": {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "123"},
                      "contacts": [{"wa_id": "258851234567", "profile": {"name": "Carla"}}],
                      "messages": list(mensagens)}}]}]}


def _assinar(corpo: bytes) -> dict:
    return {"x-hub-signature-256": "sha256=" + hmac.new(SEGREDO.encode(), corpo, hashlib.sha256).hexdigest(),
            "content-type": "application/json"}


def _app(tmp_path, canal, respostas):
    loja = Loja(tmp_path / "loja.json", relogio=lambda: AGORA)
    falso = ClaudeFalso(respostas)
    motor = Motor(loja, tmp_path / "conversas", cliente=falso)
    return TestClient(criar_app(motor, canal, VERIFICA, SEGREDO)), falso


def test_verificacao_do_webhook(tmp_path, canal):
    cliente, _ = _app(tmp_path, canal, [])
    ok = cliente.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": VERIFICA,
                                         "hub.challenge": "12345"})
    assert ok.status_code == 200 and ok.text == "12345"
    errado = cliente.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "x",
                                             "hub.challenge": "1"})
    assert errado.status_code == 403


def test_mensagem_de_texto_recebe_resposta(tmp_path, canal, meta):
    cliente, falso = _app(tmp_path, canal, [_msg(_texto("Oi, Carla! Que tipo de livro você procura?"))])
    msg = {"from": "258851234567", "id": "wamid.A", "timestamp": "1", "type": "text", "text": {"body": "oi"}}
    corpo = json.dumps(_webhook(msg)).encode()

    r = cliente.post("/webhook", content=corpo, headers=_assinar(corpo))
    assert r.status_code == 200
    assert meta.envios[0] == {"messaging_product": "whatsapp", "status": "read", "message_id": "wamid.A"}
    assert meta.envios[1]["to"] == "258851234567"
    assert meta.envios[1]["text"]["body"] == "Oi, Carla! Que tipo de livro você procura?"
    assert falso.chamadas[0][0] == {"role": "user", "content": "oi"}

    # a Meta reenviou a mesma mensagem: não responde de novo
    cliente.post("/webhook", content=corpo, headers=_assinar(corpo))
    assert len(meta.envios) == 2


def test_assinatura_invalida_e_recusada(tmp_path, canal, meta):
    cliente, _ = _app(tmp_path, canal, [])
    corpo = json.dumps(_webhook()).encode()
    r = cliente.post("/webhook", content=corpo, headers={"x-hub-signature-256": "sha256=errada",
                                                         "content-type": "application/json"})
    assert r.status_code == 401 and meta.envios == []


def test_audio_recebe_aviso_sem_chamar_o_claude(tmp_path, canal, meta):
    cliente, falso = _app(tmp_path, canal, [])
    msg = {"from": "258851234567", "id": "wamid.B", "type": "audio", "audio": {"id": "m1"}}
    corpo = json.dumps(_webhook(msg)).encode()
    cliente.post("/webhook", content=corpo, headers=_assinar(corpo))
    assert "texto" in meta.envios[-1]["text"]["body"] and falso.chamadas == []


def test_extrair_texto_de_botoes():
    assert extrair_texto({"type": "button", "button": {"text": "Quero pagar"}}) == "Quero pagar"
    assert extrair_texto({"type": "interactive", "interactive": {
        "type": "list_reply", "list_reply": {"id": "1", "title": "Ficção"}}}) == "Ficção"
    assert extrair_texto({"type": "image"}) is None


def test_envio_de_modelo(canal, meta):
    params = ["Ana", "Loja", "PED-1", "1.050,00", "10/11", "https://x"]
    canal.enviar_modelo("258840000001", "lembrete_pagamento", params, preencher("lembrete_pagamento", params))
    tpl = meta.envios[0]["template"]
    assert tpl["name"] == "lembrete_pagamento" and tpl["language"] == {"code": "pt_PT"}
    assert [p["text"] for p in tpl["components"][0]["parameters"]] == params


def test_textos_longos_sao_divididos():
    texto = "\n".join(["a" * 1000] * 10)
    partes = _partes(texto)
    assert all(len(p) <= LIMITE_TEXTO for p in partes) and "\n".join(partes) == texto


class AssistenteFalso:
    def __init__(self):
        self.recebidas = []

    def responder(self, conversa, texto, pessoa):
        self.recebidas.append((conversa, texto, pessoa))
        return ["Ontem: 12 documentos no ERP19."]


def test_numero_da_equipe_vai_para_o_assistente_interno(tmp_path, canal, meta):
    loja = Loja(tmp_path / "loja.json", relogio=lambda: AGORA)
    falso = ClaudeFalso([_msg(_texto("Olá! Procura algum livro?"))])
    assistente = AssistenteFalso()
    app = criar_app(Motor(loja, tmp_path / "c", cliente=falso), canal, VERIFICA, SEGREDO,
                    assistente, {"258840000010": "Rogério"})
    cliente = TestClient(app)
    for remetente, mid in (("258840000010", "wamid.E"), ("258851234567", "wamid.F")):
        msg = {"from": remetente, "id": mid, "type": "text", "text": {"body": "vendas de ontem?"}}
        corpo = json.dumps(_webhook(msg)).encode()
        cliente.post("/webhook", content=corpo, headers=_assinar(corpo))
    assert assistente.recebidas == [("whatsapp-258840000010", "vendas de ontem?", "Rogério")]
    respostas = {e["to"]: e["text"]["body"] for e in meta.envios if e.get("type") == "text"}
    assert respostas == {"258840000010": "Ontem: 12 documentos no ERP19.",
                         "258851234567": "Olá! Procura algum livro?"}
