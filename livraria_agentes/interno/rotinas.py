"""Rotinas automáticas do dia. Agende com cron (Linux/Mac) ou com o Agendador de Tarefas (Windows):

    python -m livraria_agentes.interno.rotinas manha --whatsapp   # 7h30: tarefas da equipa, stock, post do dia
    python -m livraria_agentes.interno.rotinas noite --whatsapp   # 18h: relatório do dia para o responsável

Sem --whatsapp, o resultado só aparece no terminal.

Quem recebe: EQUIPE_WHATSAPP (cada pessoa recebe as suas tarefas de manhã) e DONO_WHATSAPP (recebe o
resumo da manhã e o relatório da noite; se não estiver definido, vai para a primeira pessoa da equipa).

No WhatsApp, uma mensagem livre só chega se a pessoa falou com o número nas últimas 24h. Se não chegar,
é enviado o modelo aprovado `aviso_resumo_diario` ("Olá, {{1}}! O resumo diário da livraria está pronto.
Responda *resumo* para receber.") e o texto fica guardado: quando a pessoa responder, o assistente envia.
"""

from __future__ import annotations

import argparse
import logging
import os

import httpx

from ..agentes import NOME_LOJA
from ..config import abrir
from ..loja import Loja
from . import abrir_assistente, equipe_whatsapp
from .assistente import Assistente

log = logging.getLogger(__name__)
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

PEDIDO_MANHA = """\
Rotina das 7h30 ({dia}). Prepare o arranque do dia da {loja}:
1. Importe os relatórios novos dos ERPs, se houver.
2. Livros com stock de 3 unidades ou menos, e o que está esgotado: diga o que convém encomendar.
3. Tarefas pendentes da equipa: quantas há, quais estão sem responsável e uma sugestão de quem faz o quê
   (não atribua sozinho; a equipa confirma).
4. Pedidos à espera de pagamento ou de confirmação, e pagamentos "em verificação" para conferir.
5. Crie o rascunho do post de hoje com marketing_metodo e post_salvar, seguindo o calendário da casa
   (segunda: comece a semana com a Palavra; quarta: livro da semana; sexta: presente que edifica;
   domingo: versículo e Escola Dominical; nos outros dias, conteúdo útil). Use só livros com stock.
Mensagem curta para WhatsApp, a começar com "Paz do Senhor!"."""

PEDIDO_NOITE = """\
Relatório das 18h ({dia}) da {loja}, para o responsável. Use só dados das ferramentas:
1. Vendas de hoje: entradas do financeiro de hoje (por forma de pagamento), pedidos do WhatsApp pagos hoje e,
   se houver relatório do ERP22 de hoje importado, o total do ERP. Diga de onde vem cada número.
2. Saídas de hoje registadas no financeiro e o saldo do dia.
3. Contactos novos no WhatsApp e pedidos novos.
4. Stock baixo (3 ou menos) e esgotados.
5. Tarefas pendentes da equipa (quem tem o quê).
6. Pedidos de oração recebidos hoje (quantos; não exponha detalhes pessoais além do necessário).
7. E-mails importantes de hoje e faturas novas, se o e-mail estiver configurado.
Formato WhatsApp curto, com ✅ ⚠️ 📋 🙏, a começar com "Paz do Senhor!" e terminar com "Deus abençoe!"."""


def destinatario_principal() -> tuple[str, str] | None:
    dono = "".join(c for c in os.environ.get("DONO_WHATSAPP", "") if c.isdigit())
    equipe = equipe_whatsapp()
    if dono:
        return dono, equipe.get(dono, "responsável")
    return next(iter(equipe.items()), None)


def mensagens_de_tarefas(loja: Loja) -> dict[str, str]:
    """Mensagem de manhã para cada pessoa da equipa, com as suas tarefas pendentes (sem usar IA)."""
    sem_responsavel = loja.listar_tarefas(None, True)
    sem_responsavel = [t for t in sem_responsavel if not t["responsavel"]]
    mensagens = {}
    for telefone, nome in equipe_whatsapp().items():
        minhas = loja.listar_tarefas(nome, True)
        linhas = [f"Paz do Senhor, {nome.split()[0]}! Bom dia."]
        if minhas:
            linhas.append("As suas tarefas de hoje:")
            linhas += [f"• {t['descricao']}" + (f" (até {t['prazo']})" if t["prazo"] else "") for t in minhas]
        else:
            linhas.append("Não tem tarefas atribuídas para hoje.")
        if sem_responsavel:
            linhas.append(f"Há {len(sem_responsavel)} tarefa(s) da loja ainda sem responsável.")
        linhas.append("Quando terminar uma, avise aqui. Deus abençoe!")
        mensagens[telefone] = "\n".join(linhas)
    return mensagens


def _enviar(canal, assistente: Assistente, telefone: str, nome: str, texto: str) -> None:
    estado = assistente.carregar(f"whatsapp-{telefone}")
    estado.setdefault("resumos_pendentes", []).append(texto)
    assistente.salvar(estado)
    try:
        canal.enviar(telefone, texto)
    except httpx.HTTPStatusError:
        log.info("Fora da janela de 24h com %s: enviando aviso por modelo", telefone)
        canal.enviar_modelo(telefone, "aviso_resumo_diario", [nome.split()[0]],
                            f"Olá, {nome}! O resumo diário da livraria está pronto. Responda *resumo* para receber.")


def rodar(rotina: str, loja: Loja, assistente: Assistente, canal=None) -> dict:
    momento = loja.relogio()
    dia = f"{DIAS[momento.weekday()]}, {momento:%d/%m/%Y}"
    pedido = (PEDIDO_MANHA if rotina == "manha" else PEDIDO_NOITE).format(dia=dia, loja=NOME_LOJA)
    resumo = "\n\n".join(assistente.responder(f"rotina-{rotina}-{momento.date().isoformat()}", pedido,
                                              "rotina automática"))
    envios = {}
    principal = destinatario_principal()
    if principal:
        envios[principal[0]] = (principal[1], resumo)
    if rotina == "manha":
        for telefone, texto in mensagens_de_tarefas(loja).items():
            nome = equipe_whatsapp()[telefone]
            if telefone in envios:
                texto = envios[telefone][1] + "\n\n" + texto
            envios[telefone] = (nome, texto)
    if canal is not None:
        for telefone, (nome, texto) in envios.items():
            _enviar(canal, assistente, telefone, nome, texto)
    return {"resumo": resumo, "envios": {t: texto for t, (_, texto) in envios.items()}}


def main() -> None:
    parser = argparse.ArgumentParser(description="Rotinas do dia da livraria")
    parser.add_argument("rotina", choices=["manha", "noite"])
    parser.add_argument("--whatsapp", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    loja, _ = abrir()
    assistente = abrir_assistente(loja)
    canal = None
    if args.whatsapp:
        from ..canal import CanalWhatsApp

        canal = CanalWhatsApp.do_ambiente()
    resultado = rodar(args.rotina, loja, assistente, canal)
    if not args.whatsapp:
        print(resultado["resumo"])
        for telefone, texto in resultado["envios"].items():
            print(f"\n--- para {telefone} ---\n{texto}")


if __name__ == "__main__":
    main()
