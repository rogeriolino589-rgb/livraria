"""Canal de envio de mensagens.

Por enquanto as mensagens só aparecem no terminal. Para ligar no WhatsApp,
crie uma classe com o mesmo método `enviar` que chame a API oficial do
WhatsApp Business (Cloud API da Meta), e um pequeno servidor web que receba
as mensagens dos clientes (webhook) e chame `Motor.responder(telefone, texto)`.
"""

from __future__ import annotations

from typing import Protocol


class Canal(Protocol):
    def enviar(self, telefone: str, texto: str) -> None: ...


class CanalTerminal:
    def enviar(self, telefone: str, texto: str) -> None:
        print(f"\n📤 Para {telefone}:\n{texto}\n")
