"""Servidor do webhook do WhatsApp (API oficial da Meta).

    python -m livraria_agentes.servidor

Variáveis de ambiente:
    ANTHROPIC_API_KEY         chave da API do Claude
    WHATSAPP_TOKEN            token de acesso (de preferência o permanente, de um usuário do sistema)
    WHATSAPP_PHONE_NUMBER_ID  id do número (WhatsApp > Configuração da API, no app da Meta)
    WHATSAPP_VERIFY_TOKEN     uma senha que você inventa e repete na configuração do webhook na Meta
    WHATSAPP_APP_SECRET       chave secreta do app (Configurações do app > Básico)
    EQUIPE_WHATSAPP           números da equipe que falam com o assistente interno, ex.: "258840000010:Rogério"
    PORT                      porta HTTP (padrão 8000)

Na Meta, configure a URL de callback como https://SEU-DOMINIO/webhook e assine o campo "messages".
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import threading
from collections import OrderedDict

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse

from .canal import CanalWhatsApp
from .motor import Motor
from .textos import t

log = logging.getLogger(__name__)

MSG_SO_TEXTO = t("so_texto")


class _Recentes:
    """Lembra os ids das últimas mensagens: a Meta às vezes entrega a mesma mensagem duas vezes."""

    def __init__(self, limite: int = 5000):
        self.ids: OrderedDict[str, None] = OrderedDict()
        self.limite = limite
        self.trava = threading.Lock()

    def novo(self, mensagem_id: str) -> bool:
        with self.trava:
            if mensagem_id in self.ids:
                return False
            self.ids[mensagem_id] = None
            if len(self.ids) > self.limite:
                self.ids.popitem(last=False)
            return True


def extrair_texto(msg: dict) -> str | None:
    """Texto da mensagem do cliente, incluindo cliques em botões e listas. None se não for texto."""
    tipo = msg.get("type")
    if tipo == "text":
        return msg["text"]["body"]
    if tipo == "button":  # botão de resposta rápida de um modelo
        return msg["button"]["text"]
    if tipo == "interactive":
        interativo = msg["interactive"]
        resposta = interativo.get(interativo.get("type"), {})
        return resposta.get("title")
    return None


def assinatura_valida(corpo: bytes, cabecalho: str | None, segredo: str) -> bool:
    if not cabecalho or not cabecalho.startswith("sha256="):
        return False
    esperado = hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, cabecalho.removeprefix("sha256="))


def criar_app(motor: Motor, canal: CanalWhatsApp, verify_token: str, app_secret: str,
              assistente=None, equipe: dict[str, str] | None = None) -> FastAPI:
    """`equipe` ({telefone: nome}) conversa com o `assistente` interno; os demais números, com os agentes
    de atendimento."""
    equipe = equipe or {}
    app = FastAPI(title="Livraria - webhook do WhatsApp", docs_url=None, redoc_url=None)
    recentes = _Recentes()
    travas: dict[str, threading.Lock] = {}
    travas_trava = threading.Lock()

    def trava_do(telefone: str) -> threading.Lock:
        with travas_trava:
            return travas.setdefault(telefone, threading.Lock())

    def atender(telefone: str, mensagem_id: str, texto: str | None, de: str | None = None) -> None:
        # Uma mensagem por vez para cada cliente, na ordem em que chegaram.
        with trava_do(telefone):
            try:
                canal.marcar_lida(mensagem_id, de)
                if texto is None:
                    canal.enviar(telefone, MSG_SO_TEXTO, de)
                    return
                if telefone in equipe and assistente is not None:
                    textos = assistente.responder(f"whatsapp-{telefone}", texto, equipe[telefone])
                else:
                    textos = motor.responder(telefone, texto).textos
                for parte in textos:
                    canal.enviar(telefone, parte, de)
            except Exception:
                log.exception("Erro ao atender %s (mensagem %s)", telefone, mensagem_id)

    @app.get("/")
    def saude() -> dict:
        return {"ok": True}

    @app.get("/webhook")
    def verificar(request: Request) -> PlainTextResponse:
        """A Meta chama este endereço uma vez, ao configurar o webhook."""
        p = request.query_params
        if p.get("hub.mode") == "subscribe" and hmac.compare_digest(p.get("hub.verify_token", ""), verify_token):
            return PlainTextResponse(p.get("hub.challenge", ""))
        raise HTTPException(status_code=403, detail="Token de verificação inválido")

    @app.post("/webhook")
    async def receber(request: Request, tarefas: BackgroundTasks) -> dict:
        corpo = await request.body()
        if not assinatura_valida(corpo, request.headers.get("x-hub-signature-256"), app_secret):
            raise HTTPException(status_code=401, detail="Assinatura inválida")
        dados = await request.json()
        for entrada in dados.get("entry", []):
            for mudanca in entrada.get("changes", []):
                valor = mudanca.get("value", {})
                for msg in valor.get("messages", []):
                    if not recentes.novo(msg["id"]):
                        continue
                    # Responde 200 na hora; o Claude roda em segundo plano (a Meta reenvia se demorar).
                    # responde pelo mesmo número da loja em que o cliente escreveu (igrejas, retalho, revenda...)
                    de = valor.get("metadata", {}).get("phone_number_id")
                    tarefas.add_task(atender, msg["from"], msg["id"], extrair_texto(msg), de)
                # "statuses" (entregue, lido, falhou) só aparecem no log.
                for status in valor.get("statuses", []):
                    if status.get("status") == "failed":
                        log.warning("Falha na entrega para %s: %s", status.get("recipient_id"), status.get("errors"))
        return {"ok": True}

    return app


def main() -> None:
    import uvicorn

    from .config import abrir

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    faltando = [v for v in ("ANTHROPIC_API_KEY", "WHATSAPP_VERIFY_TOKEN", "WHATSAPP_APP_SECRET")
                if not os.environ.get(v)]
    if faltando:
        raise SystemExit(f"Configure as variáveis de ambiente: {', '.join(faltando)}")
    from .interno import abrir_assistente, equipe_whatsapp

    from .vendedores import Avisos

    loja, motor = abrir()
    canal = CanalWhatsApp.do_ambiente()
    motor.avisos = Avisos(canal.enviar, enviar_modelo=canal.enviar_modelo)  # avisa o vendedor da linha do cliente (config/vendedores.json)
    equipe = equipe_whatsapp()
    if equipe:
        log.info("Equipe com acesso ao assistente interno: %s", ", ".join(equipe.values()))
    app = criar_app(motor, canal, os.environ["WHATSAPP_VERIFY_TOKEN"],
                    os.environ["WHATSAPP_APP_SECRET"], abrir_assistente(loja) if equipe else None, equipe)
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
