"""Chat da equipe com o assistente interno, no terminal.

    python -m livraria_agentes.interno.chat --nome Rogério

Comandos: /importar ARQUIVO erp19|erp22, /reiniciar, /sair.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from ..config import abrir
from . import abrir_assistente
from .base import ErroDados


def main() -> None:
    parser = argparse.ArgumentParser(description="Assistente interno da livraria")
    parser.add_argument("--nome", default="equipe", help="Seu nome")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.WARNING)

    loja, _ = abrir()
    assistente = abrir_assistente(loja)
    conversa = f"terminal-{args.nome}"
    if assistente.ctx.caixa is None:
        print("   (e-mail não configurado: defina IMAP_HOST, IMAP_USUARIO e IMAP_SENHA)")
    print("🧑‍💼 Assistente interno. Comandos: /importar ARQUIVO erp19|erp22, /reiniciar, /sair\n")
    while True:
        try:
            texto = input(f"{args.nome}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not texto:
            continue
        if texto == "/sair":
            break
        if texto == "/reiniciar":
            assistente.reiniciar(conversa)
            print("   (conversa apagada)")
            continue
        if texto.startswith("/importar"):
            partes = texto.split()
            if len(partes) != 3:
                print("   uso: /importar caminho/do/relatorio.xlsx erp19")
                continue
            try:
                print(json.dumps(assistente.ctx.base.importar_relatorio(Path(partes[1]), partes[2]),
                                 ensure_ascii=False, indent=1))
            except (ErroDados, OSError) as erro:
                print(f"   erro: {erro}")
            continue
        try:
            respostas = assistente.responder(conversa, texto, args.nome)
        except TypeError as erro:
            if "authentication" not in str(erro):
                raise
            print("   ⚠️  Falta a chave da API do Claude: export ANTHROPIC_API_KEY=sua-chave")
            break
        for msg in respostas:
            print(f"\nAssistente: {msg}\n")


if __name__ == "__main__":
    main()
