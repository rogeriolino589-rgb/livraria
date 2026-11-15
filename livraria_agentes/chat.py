"""Simulador de WhatsApp no terminal.

    python -m livraria_agentes.chat --telefone 5511900000001

Comandos: /agente (mostra o agente ativo), /reiniciar (apaga a conversa), /sair.
"""

from __future__ import annotations

import argparse
import logging

from .agentes import AGENTES, NOME_LOJA
from .config import abrir


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Chat simulado com os agentes da {NOME_LOJA}")
    parser.add_argument("--telefone", default="5511999990000", help="Número do cliente simulado")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING)

    loja, motor = abrir()
    agente = motor.carregar(args.telefone)["agente"]
    print(f"💬 {NOME_LOJA}: você é o cliente {args.telefone}. Comandos: /agente, /reiniciar, /sair\n")
    while True:
        try:
            texto = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not texto:
            continue
        if texto == "/sair":
            break
        if texto == "/agente":
            print(f"   (agente ativo: {AGENTES[agente]['titulo']})")
            continue
        if texto == "/reiniciar":
            motor.reiniciar(args.telefone)
            agente = motor.carregar(args.telefone)["agente"]
            print("   (conversa apagada)")
            continue
        try:
            resposta = motor.responder(args.telefone, texto)
        except TypeError as erro:
            if "authentication" not in str(erro):
                raise
            print("   ⚠️  Falta a chave da API do Claude. Crie uma em https://platform.claude.com e rode:\n"
                  "   export ANTHROPIC_API_KEY=sua-chave")
            break
        if resposta.agente != agente:
            print(f"   (↪ conversa passou para: {AGENTES[resposta.agente]['titulo']})")
            agente = resposta.agente
        for msg in resposta.textos:
            print(f"Livraria: {msg}\n")


if __name__ == "__main__":
    main()
