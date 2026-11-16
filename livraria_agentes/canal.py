"""Canais de envio de mensagens: terminal (testes) e WhatsApp (API oficial da Meta)."""

from __future__ import annotations

import logging
import os
from typing import Protocol

import httpx

from .pais import PAIS

log = logging.getLogger(__name__)

LIMITE_TEXTO = 4096  # limite do WhatsApp por mensagem de texto


class Canal(Protocol):
    def enviar(self, telefone: str, texto: str) -> None:
        """Mensagem de texto livre (resposta dentro da janela de 24h do cliente)."""

    def enviar_modelo(self, telefone: str, modelo: str, parametros: list[str], texto: str) -> None:
        """Mensagem iniciada pela loja: no WhatsApp precisa ser um modelo aprovado pela Meta.
        `texto` é a versão já preenchida, usada no terminal e guardada no histórico."""


class CanalTerminal:
    def enviar(self, telefone: str, texto: str) -> None:
        print(f"\n📤 Para {telefone}:\n{texto}\n")

    def enviar_modelo(self, telefone: str, modelo: str, parametros: list[str], texto: str) -> None:
        print(f"\n📤 Para {telefone} (modelo {modelo}):\n{texto}\n")

    def marcar_lida(self, mensagem_id: str) -> None:
        pass


def _partes(texto: str) -> list[str]:
    """Divide textos longos em pedaços aceitos pelo WhatsApp, quebrando em parágrafos."""
    partes, atual = [], ""
    for paragrafo in texto.split("\n"):
        while len(paragrafo) > LIMITE_TEXTO:
            if atual:
                partes.append(atual)
                atual = ""
            partes.append(paragrafo[:LIMITE_TEXTO])
            paragrafo = paragrafo[LIMITE_TEXTO:]
        candidato = f"{atual}\n{paragrafo}" if atual else paragrafo
        if len(candidato) > LIMITE_TEXTO:
            partes.append(atual)
            atual = paragrafo
        else:
            atual = candidato
    if atual.strip():
        partes.append(atual)
    return partes


class CanalWhatsApp:
    """Envia mensagens pela WhatsApp Cloud API (graph.facebook.com)."""

    def __init__(self, token: str, phone_number_id: str, versao: str = "v23.0",
                 idioma_modelos: str | None = None, cliente_http: httpx.Client | None = None):
        self.url = f"https://graph.facebook.com/{versao}/{phone_number_id}/messages"
        self.idioma = idioma_modelos or PAIS.idioma_modelos_whatsapp
        self.http = cliente_http or httpx.Client(timeout=20)
        self.http.headers["Authorization"] = f"Bearer {token}"

    @classmethod
    def do_ambiente(cls) -> CanalWhatsApp:
        faltando = [v for v in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID") if not os.environ.get(v)]
        if faltando:
            raise SystemExit(f"Configure as variáveis de ambiente: {', '.join(faltando)}")
        return cls(os.environ["WHATSAPP_TOKEN"], os.environ["WHATSAPP_PHONE_NUMBER_ID"],
                   os.environ.get("WHATSAPP_API_VERSION", "v23.0"))

    def _post(self, corpo: dict) -> dict:
        resp = self.http.post(self.url, json={"messaging_product": "whatsapp", **corpo})
        if resp.is_error:
            log.error("WhatsApp recusou o envio (%s): %s", resp.status_code, resp.text)
            resp.raise_for_status()
        return resp.json()

    def enviar(self, telefone: str, texto: str) -> None:
        for parte in _partes(texto):
            self._post({"recipient_type": "individual", "to": telefone, "type": "text",
                        "text": {"body": parte, "preview_url": True}})

    def enviar_modelo(self, telefone: str, modelo: str, parametros: list[str], texto: str) -> None:
        self._post({"to": telefone, "type": "template", "template": {
            "name": modelo, "language": {"code": self.idioma},
            "components": [{"type": "body",
                            "parameters": [{"type": "text", "text": p} for p in parametros]}]}})

    def marcar_lida(self, mensagem_id: str) -> None:
        """Mostra os dois tiques azuis para o cliente. Falha aqui não impede a resposta."""
        try:
            self._post({"status": "read", "message_id": mensagem_id})
        except httpx.HTTPError:
            log.warning("Não consegui marcar a mensagem %s como lida", mensagem_id)
