"""Mensagens fixas que os clientes e a equipa recebem, por língua (pt, en, fr).

As respostas dos agentes são escritas pelo Claude na língua do cliente; aqui ficam só os textos que o
sistema envia sem passar pelo Claude (avisos de erro, lembretes por modelo aprovado, tarefas da manhã).
"""

from __future__ import annotations

from .pais import PAIS

TEXTOS = {
    "pt": {
        "instabilidade": "Desculpe, tivemos uma falha técnica. Pode enviar a sua mensagem de novo dentro de instantes? 🙏",
        "recusa": "Desculpe, não consigo ajudar com isso por aqui. Posso ajudar com livros, pedidos ou marcações?",
        "verificar_equipa": "Só um instante, vou verificar isso com a equipa.",
        "so_texto": "Por enquanto só consigo ler mensagens de texto 🙂 Pode escrever o que precisa?",
        "modelo_lembrete_pagamento": (
            "Olá, {{1}}! Aqui é da {{2}}. O pagamento do seu pedido {{3}} ({{4}}) venceu em {{5}}. "
            "Ainda quer os livros? Este é o link para pagar: {{6}}. Se já pagou ou quer cancelar, basta responder aqui."),
        "modelo_pos_venda": (
            "Olá, {{1}}! Aqui é da {{2}}. Recebeu {{3}} há alguns dias: está a gostar da leitura? "
            "Se puder, responda com uma nota de 1 a 5. E se algo veio errado, diga-nos e resolvemos."),
        "os_seus_livros": "os seus livros",
        "sem_nome": "tudo bem",
        "aviso_resumo": "Olá, {nome}! O resumo diário da livraria está pronto. Responda *resumo* para receber.",
        "tarefas_bom_dia": "Paz do Senhor, {nome}! Bom dia.",
        "tarefas_lista": "As suas tarefas de hoje:",
        "tarefas_ate": " (até {prazo})",
        "tarefas_nenhuma": "Não tem tarefas atribuídas para hoje.",
        "tarefas_sem_responsavel": "Há {n} tarefa(s) da loja ainda sem responsável.",
        "tarefas_fim": "Quando terminar uma, avise aqui. Deus abençoe!",
    },
    "en": {
        "instabilidade": "Sorry, we had a technical problem. Could you send your message again in a moment? 🙏",
        "recusa": "Sorry, I can't help with that here. Can I help you with books, orders or appointments?",
        "verificar_equipa": "Just a moment, I'll check this with the team.",
        "so_texto": "For now I can only read text messages 🙂 Could you type what you need?",
        "modelo_lembrete_pagamento": (
            "Hello, {{1}}! This is {{2}}. The payment for your order {{3}} ({{4}}) was due on {{5}}. "
            "Do you still want the books? Here is the payment link: {{6}}. If you have paid or want to cancel, "
            "just reply here."),
        "modelo_pos_venda": (
            "Hello, {{1}}! This is {{2}}. You received {{3}} a few days ago: are you enjoying it? "
            "If you can, reply with a score from 1 to 5. And if anything went wrong, tell us and we'll fix it."),
        "os_seus_livros": "your books",
        "sem_nome": "there",
        "aviso_resumo": "Hello, {nome}! The bookshop's daily summary is ready. Reply *summary* to receive it.",
        "tarefas_bom_dia": "Blessings, {nome}! Good morning.",
        "tarefas_lista": "Your tasks for today:",
        "tarefas_ate": " (by {prazo})",
        "tarefas_nenhuma": "You have no tasks assigned for today.",
        "tarefas_sem_responsavel": "There are {n} shop task(s) with no one assigned yet.",
        "tarefas_fim": "When you finish one, let us know here. God bless!",
    },
    "fr": {
        "instabilidade": "Désolé, nous avons eu un problème technique. Pouvez-vous renvoyer votre message dans un instant ? 🙏",
        "recusa": "Désolé, je ne peux pas vous aider pour cela ici. Puis-je vous aider pour des livres, des commandes ou des rendez-vous ?",
        "verificar_equipa": "Un instant, je vérifie cela avec l'équipe.",
        "so_texto": "Pour le moment, je ne lis que les messages texte 🙂 Pouvez-vous écrire ce dont vous avez besoin ?",
        "modelo_lembrete_pagamento": (
            "Bonjour {{1}} ! Ici {{2}}. Le paiement de votre commande {{3}} ({{4}}) était dû le {{5}}. "
            "Voulez-vous toujours les livres ? Voici le lien de paiement : {{6}}. Si vous avez déjà payé ou "
            "souhaitez annuler, répondez simplement ici."),
        "modelo_pos_venda": (
            "Bonjour {{1}} ! Ici {{2}}. Vous avez reçu {{3}} il y a quelques jours : la lecture vous plaît-elle ? "
            "Si possible, répondez avec une note de 1 à 5. Et si quelque chose ne va pas, dites-le-nous."),
        "os_seus_livros": "vos livres",
        "sem_nome": "",
        "aviso_resumo": "Bonjour {nome} ! Le résumé du jour de la librairie est prêt. Répondez *résumé* pour le recevoir.",
        "tarefas_bom_dia": "Que la paix du Seigneur soit avec vous, {nome} ! Bonjour.",
        "tarefas_lista": "Vos tâches d'aujourd'hui :",
        "tarefas_ate": " (avant le {prazo})",
        "tarefas_nenhuma": "Vous n'avez pas de tâche attribuée aujourd'hui.",
        "tarefas_sem_responsavel": "Il y a {n} tâche(s) de la librairie sans responsable.",
        "tarefas_fim": "Quand vous en terminez une, prévenez ici. Que Dieu vous bénisse !",
    },
}


def t(chave: str, lingua: str | None = None, **valores) -> str:
    """Texto na língua dos clientes do país (ou na indicada); cai para português se faltar."""
    lingua = lingua or PAIS.lingua_clientes
    texto = TEXTOS.get(lingua, TEXTOS["pt"]).get(chave) or TEXTOS["pt"][chave]
    return texto.format(**valores) if valores else texto
