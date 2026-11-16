"""Mensagens automáticas: lembretes de cobrança e pós-venda.

Rode uma vez por dia (por exemplo com cron):
    python -m livraria_agentes.lembretes             # mostra no terminal
    python -m livraria_agentes.lembretes --whatsapp  # envia de verdade

No WhatsApp, mensagens que a loja envia primeiro precisam ser modelos
aprovados pela Meta. Cadastre no WhatsApp Manager, na língua do país (PAIS.idioma_modelos_whatsapp), os
dois modelos abaixo com o mesmo nome e os mesmos {{n}}. Quando o cliente
responde, o agente de cobrança ou de pós-venda assume a conversa já sabendo o
que foi enviado.
"""

from __future__ import annotations

import argparse
import re
from datetime import date

from .canal import Canal
from .pais import PAIS
from .textos import t
from .loja import Loja
from .motor import Motor

# nome do modelo na Meta -> texto com {{1}}, {{2}}... (categoria: Utilidade)
MODELOS = {
    "lembrete_pagamento": t("modelo_lembrete_pagamento"),
    "pos_venda": t("modelo_pos_venda"),
}


def preencher(modelo: str, parametros: list[str]) -> str:
    return re.sub(r"\{\{(\d+)\}\}", lambda m: parametros[int(m.group(1)) - 1], MODELOS[modelo])


def _dinheiro(valor: float) -> str:
    return PAIS.dinheiro(valor, True)


def _primeiro_nome(loja: Loja, telefone: str) -> str:
    nome = loja.nome_cliente(telefone)
    return nome.split()[0] if nome else t("sem_nome")


def _enviar(canal: Canal, motor: Motor, telefone: str, modelo: str, parametros: list[str], agente: str) -> None:
    texto = preencher(modelo, parametros)
    canal.enviar_modelo(telefone, modelo, parametros, texto)
    motor.notificar(telefone, texto, agente)


def rodar(loja: Loja, motor: Motor, canal: Canal, nome_loja: str) -> int:
    enviados = 0
    for p in loja.pedidos_para_cobrar():
        _enviar(canal, motor, p["telefone"], "lembrete_pagamento", [
            _primeiro_nome(loja, p["telefone"]), nome_loja, p["id"], _dinheiro(p["total"]),
            date.fromisoformat(p["vencimento"]).strftime("%d/%m"), loja.link_pagamento(p)], "cobranca")
        loja.marcar_lembrete(p["id"], "cobranca")
        enviados += 1
    for p in loja.pedidos_para_pos_venda():
        titulo = p["itens"][0]["titulo"] if len(p["itens"]) == 1 else t("os_seus_livros")
        _enviar(canal, motor, p["telefone"], "pos_venda",
                [_primeiro_nome(loja, p["telefone"]), nome_loja, titulo], "suporte_posvenda")
        loja.marcar_lembrete(p["id"], "pos_venda")
        enviados += 1
    return enviados


def main() -> None:
    from .agentes import NOME_LOJA
    from .canal import CanalTerminal, CanalWhatsApp
    from .config import abrir

    parser = argparse.ArgumentParser(description="Envia lembretes de cobrança e pós-venda")
    parser.add_argument("--whatsapp", action="store_true", help="Envia pelo WhatsApp em vez do terminal")
    args = parser.parse_args()
    canal = CanalWhatsApp.do_ambiente() if args.whatsapp else CanalTerminal()
    loja, motor = abrir()
    total = rodar(loja, motor, canal, NOME_LOJA)
    print(f"{total} mensagem(ns) automática(s) enviada(s).")


if __name__ == "__main__":
    main()
