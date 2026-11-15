"""Mensagens automáticas: lembretes de cobrança e pós-venda.

Rode uma vez por dia (por exemplo com cron):
    python -m livraria_agentes.lembretes

Os textos são modelos fixos de propósito: no WhatsApp oficial, mensagens que a
empresa envia primeiro (fora da janela de 24h) precisam ser modelos aprovados
pela Meta. Quando o cliente responde, o agente de cobrança ou de pós-venda
assume a conversa já sabendo o que foi enviado.
"""

from __future__ import annotations

from datetime import date

from .canal import Canal
from .config import abrir
from .loja import Loja
from .motor import Motor

MODELO_COBRANCA = (
    "Olá, {nome}! Aqui é da {loja}. O pagamento do seu pedido {pedido} (R$ {total}) venceu em {vencimento}. "
    "Ainda quer os livros? Este é o link para pagar: {link}. Se já pagou ou quer cancelar, é só responder aqui."
)
MODELO_POS_VENDA = (
    "Olá, {nome}! Aqui é da {loja}. Você recebeu {titulo} há alguns dias: está gostando da leitura? "
    "Se puder, responda com uma nota de 1 a 5. E se algo veio errado, é só contar que a gente resolve."
)


def _reais(valor: float) -> str:
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def rodar(loja: Loja, motor: Motor, canal: Canal, nome_loja: str) -> int:
    enviados = 0
    for p in loja.pedidos_para_cobrar():
        texto = MODELO_COBRANCA.format(
            nome=(loja.nome_cliente(p["telefone"]) or "tudo bem").split()[0], loja=nome_loja, pedido=p["id"],
            total=_reais(p["total"]), vencimento=date.fromisoformat(p["vencimento"]).strftime("%d/%m"),
            link=loja.link_pagamento(p))
        canal.enviar(p["telefone"], texto)
        motor.notificar(p["telefone"], texto, "cobranca")
        loja.marcar_lembrete(p["id"], "cobranca")
        enviados += 1
    for p in loja.pedidos_para_pos_venda():
        texto = MODELO_POS_VENDA.format(
            nome=(loja.nome_cliente(p["telefone"]) or "tudo bem").split()[0], loja=nome_loja,
            titulo=p["itens"][0]["titulo"] if len(p["itens"]) == 1 else "seus livros")
        canal.enviar(p["telefone"], texto)
        motor.notificar(p["telefone"], texto, "suporte_posvenda")
        loja.marcar_lembrete(p["id"], "pos_venda")
        enviados += 1
    return enviados


def main() -> None:
    from .agentes import NOME_LOJA
    from .canal import CanalTerminal

    loja, motor = abrir()
    total = rodar(loja, motor, CanalTerminal(), NOME_LOJA)
    print(f"{total} mensagem(ns) automática(s) enviada(s).")


if __name__ == "__main__":
    main()
