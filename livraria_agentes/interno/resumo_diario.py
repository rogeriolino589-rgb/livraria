"""Resumo diário para a equipe. Rode todo dia de manhã (por exemplo com cron):

    python -m livraria_agentes.interno.resumo_diario             # mostra no terminal
    python -m livraria_agentes.interno.resumo_diario --whatsapp  # envia para EQUIPE_WHATSAPP

No WhatsApp, uma mensagem livre só chega se a pessoa falou com o número nas últimas 24h.
Se não chegar, é enviado o modelo aprovado `aviso_resumo_diario` ("Olá, {{1}}! O resumo
diário da livraria está pronto. Responda *resumo* para receber.").
"""

from __future__ import annotations

import argparse
import logging

import httpx

from ..config import abrir
from . import abrir_assistente, equipe_whatsapp

PEDIDO = """\
Prepare o resumo diário da livraria para a equipe:
1. Importe os relatórios novos dos ERPs, se houver.
2. Vendas de ontem e do mês até ontem (ERP22), com os 3 melhores vendedores e províncias, comparando
   com o mesmo mês do ano anterior (se for antes de ago/2022, avise que o número vem do ERP19).
3. E-mails desde ontem: o que pede ação, faturas e comprovantes (copie os documentos, registre as
   faturas e mostre a que documento dos ERPs podem corresponder) e qualquer suspeita de fraude.
4. Atendimento por WhatsApp: pedidos, pagamentos para conferir, clientes esperando atendente, chamados.
5. Livros com estoque de 3 unidades ou menos.
Seja objetivo; se alguma fonte não estiver configurada ou disponível, diga em uma linha e siga."""

log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Resumo diário da livraria")
    parser.add_argument("--whatsapp", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    loja, _ = abrir()
    assistente = abrir_assistente(loja)
    hoje = loja.relogio().date().isoformat()
    texto = "\n\n".join(assistente.responder(f"resumo-{hoje}", PEDIDO, "rotina automática"))
    if not args.whatsapp:
        print(texto)
        return

    from ..canal import CanalWhatsApp

    canal = CanalWhatsApp.do_ambiente()
    for telefone, nome in equipe_whatsapp().items():
        # Guarda o resumo na conversa da pessoa: se ela responder "resumo", o assistente já tem o texto.
        estado = assistente.carregar(f"whatsapp-{telefone}")
        estado.setdefault("resumos_pendentes", []).append(texto)
        assistente.salvar(estado)
        try:
            canal.enviar(telefone, texto)
        except httpx.HTTPStatusError:
            log.info("Fora da janela de 24h com %s: enviando aviso por modelo", telefone)
            canal.enviar_modelo(telefone, "aviso_resumo_diario", [nome.split()[0]],
                                f"Olá, {nome}! O resumo diário da livraria está pronto. Responda *resumo* para receber.")


if __name__ == "__main__":
    main()
