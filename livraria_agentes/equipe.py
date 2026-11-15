"""Comandos para a equipe humana.

    python -m livraria_agentes.equipe fila                       # quem pediu atendente
    python -m livraria_agentes.equipe responder 25884... "texto"  # responde pelo WhatsApp
    python -m livraria_agentes.equipe liberar 25884...           # devolve o cliente aos agentes
"""

from __future__ import annotations

import argparse

from .config import abrir


def main() -> None:
    parser = argparse.ArgumentParser(description="Atendimento humano")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("fila", help="Lista os pedidos de atendimento humano")
    r = sub.add_parser("responder", help="Envia uma mensagem ao cliente pelo WhatsApp")
    r.add_argument("telefone")
    r.add_argument("texto")
    r.add_argument("--terminal", action="store_true", help="Mostra no terminal em vez de enviar")
    lib = sub.add_parser("liberar", help="O robô volta a atender o cliente")
    lib.add_argument("telefone")
    args = parser.parse_args()

    loja, motor = abrir()
    if args.comando == "fila":
        for item in loja.dados["fila_humana"]:
            nome = loja.nome_cliente(item["telefone"]) or "sem nome"
            print(f"{item['em']}  {item['telefone']} ({nome}): {item['motivo']}")
        aguardando = [p.stem for p in motor.pasta.glob("*.json") if motor.carregar(p.stem)["aguardando_humano"]]
        print(f"\nAguardando atendente agora: {', '.join(aguardando) or 'ninguém'}")
    elif args.comando == "responder":
        from .canal import CanalTerminal, CanalWhatsApp

        canal = CanalTerminal() if args.terminal else CanalWhatsApp.do_ambiente()
        canal.enviar(args.telefone, args.texto)
        motor.registrar_resposta_humana(args.telefone, args.texto)
        print("Enviado.")
    elif args.comando == "liberar":
        motor.liberar_humano(args.telefone)
        print(f"{args.telefone} voltou a ser atendido pelos agentes.")


if __name__ == "__main__":
    main()
