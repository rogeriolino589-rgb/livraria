"""Ferramentas que os agentes podem usar.

A lista de ferramentas é a mesma para todos os agentes (assim o cache do
prompt não quebra quando um agente passa a conversa para outro). Quem pode
usar cada ferramenta é decidido aqui no código, em `agentes.PERMISSOES`.
"""

from __future__ import annotations

import json

from .loja import TIPOS_AGENDAMENTO, ErroLoja, Loja

AGENTES_VALIDOS = ["atendimento_vendas", "agendamento", "cobranca", "suporte_posvenda"]


def _ferramenta(nome: str, descricao: str, propriedades: dict) -> dict:
    return {
        "name": nome,
        "description": descricao,
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": propriedades,
            "required": list(propriedades),
            "additionalProperties": False,
        },
    }


TEXTO = {"type": "string"}
TEXTO_OU_NULO = {"type": ["string", "null"]}

FERRAMENTAS = [
    _ferramenta("buscar_livros",
                "Busca livros no catálogo por título, autor, gênero ou assunto. Retorna até 8 livros com preço e estoque.",
                {"consulta": {**TEXTO, "description": "Palavras-chave. Use '' para listar por gênero/preço."},
                 "genero": {**TEXTO_OU_NULO, "description": "Filtro de gênero, ou null."},
                 "preco_max": {"type": ["number", "null"], "description": "Preço máximo em meticais, ou null."}}),
    _ferramenta("detalhes_livro", "Mostra todos os dados de um livro, incluindo a sinopse.",
                {"livro_id": {**TEXTO, "description": "Id do livro, ex.: L001."}}),
    _ferramenta("registrar_cliente", "Salva ou atualiza o nome do cliente desta conversa.",
                {"nome": TEXTO}),
    _ferramenta("criar_pedido",
                "Cria um pedido para o cliente desta conversa e devolve o link de pagamento. "
                "Só use depois que o cliente confirmar os livros, as quantidades e a forma de entrega.",
                {"itens": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"livro_id": TEXTO, "quantidade": {"type": "integer"}},
                    "required": ["livro_id", "quantidade"], "additionalProperties": False}},
                 "entrega": {"type": "string", "enum": ["retirada", "envio"],
                             "description": "'retirada' = levantamento na loja (grátis); 'envio' = entrega ao domicílio (taxa de 250,00 MT)."}}),
    _ferramenta("consultar_pedidos", "Lista os pedidos do cliente desta conversa, com status.", {}),
    _ferramenta("cancelar_pedido", "Cancela um pedido ainda não pago do cliente desta conversa.",
                {"pedido_id": TEXTO}),
    _ferramenta("horarios_disponiveis", "Lista os horários livres na loja em uma data.",
                {"data": {**TEXTO, "description": "Data no formato AAAA-MM-DD."}}),
    _ferramenta("agendar", "Marca um horário na loja para o cliente desta conversa.",
                {"tipo": {"type": "string", "enum": list(TIPOS_AGENDAMENTO)},
                 "data_hora": {**TEXTO, "description": "Formato AAAA-MM-DDTHH:00, ex.: 2026-11-20T14:00."},
                 "observacao": TEXTO_OU_NULO}),
    _ferramenta("listar_agendamentos", "Lista os agendamentos confirmados do cliente desta conversa.", {}),
    _ferramenta("cancelar_agendamento", "Cancela um agendamento do cliente desta conversa.",
                {"agendamento_id": TEXTO}),
    _ferramenta("consultar_pendencias", "Lista os pedidos não pagos do cliente desta conversa, com dias de atraso.", {}),
    _ferramenta("gerar_link_pagamento", "Gera de novo o link de pagamento de um pedido não pago.",
                {"pedido_id": TEXTO}),
    _ferramenta("informar_pagamento",
                "Registra que o cliente DIZ ter pago. O pedido fica 'em verificação' até a equipe confirmar; "
                "nunca diga que o pagamento foi confirmado.",
                {"pedido_id": TEXTO,
                 "detalhes": {**TEXTO, "description": "O que o cliente contou: forma de pagamento, data, comprovante."}}),
    _ferramenta("abrir_chamado", "Abre um chamado de suporte (atraso, livro danificado, troca, devolução, dúvida).",
                {"assunto": TEXTO, "descricao": TEXTO, "pedido_id": TEXTO_OU_NULO}),
    _ferramenta("registrar_avaliacao", "Registra a nota (1 a 5) e o comentário do cliente sobre um pedido.",
                {"pedido_id": TEXTO, "nota": {"type": "integer"}, "comentario": TEXTO_OU_NULO}),
    _ferramenta("registrar_pedido_oracao",
                "Entrega à equipa um pedido de oração ou necessidade partilhada pelo cliente. Não é para vendas.",
                {"pedido": {**TEXTO, "description": "O pedido, nas palavras do cliente."}}),
    _ferramenta("transferir_agente",
                "Passa a conversa para outro agente da livraria quando o assunto é da área dele.",
                {"agente": {"type": "string", "enum": AGENTES_VALIDOS},
                 "motivo": {**TEXTO, "description": "Resumo do que o cliente precisa, para o próximo agente."}}),
    _ferramenta("chamar_humano",
                "Coloca a conversa na fila de um atendente humano. Use quando o cliente pedir, estiver muito "
                "insatisfeito, ou o pedido estiver fora do que as ferramentas resolvem.",
                {"motivo": TEXTO}),
]

NOMES = {f["name"] for f in FERRAMENTAS}


def executar(loja: Loja, telefone: str, nome: str, entrada: dict) -> str:
    """Executa uma ferramenta e devolve o resultado em JSON. Lança ErroLoja em erro de regra."""
    e = entrada
    if nome == "buscar_livros":
        r = loja.buscar_livros(e["consulta"], e.get("genero"), e.get("preco_max"))
    elif nome == "detalhes_livro":
        r = loja.detalhes_livro(e["livro_id"])
    elif nome == "registrar_cliente":
        r = loja.registrar_cliente(telefone, e["nome"])
    elif nome == "criar_pedido":
        r = loja.criar_pedido(telefone, e["itens"], e["entrega"])
    elif nome == "consultar_pedidos":
        r = loja.consultar_pedidos(telefone)
    elif nome == "cancelar_pedido":
        r = loja.cancelar_pedido(telefone, e["pedido_id"])
    elif nome == "horarios_disponiveis":
        r = loja.horarios_disponiveis(e["data"])
    elif nome == "agendar":
        r = loja.agendar(telefone, e["tipo"], e["data_hora"], e.get("observacao"))
    elif nome == "listar_agendamentos":
        r = loja.listar_agendamentos(telefone)
    elif nome == "cancelar_agendamento":
        r = loja.cancelar_agendamento(telefone, e["agendamento_id"])
    elif nome == "consultar_pendencias":
        r = loja.consultar_pendencias(telefone)
    elif nome == "gerar_link_pagamento":
        r = loja.gerar_link_pagamento(telefone, e["pedido_id"])
    elif nome == "informar_pagamento":
        r = loja.informar_pagamento(telefone, e["pedido_id"], e["detalhes"])
    elif nome == "abrir_chamado":
        r = loja.abrir_chamado(telefone, e["assunto"], e["descricao"], e.get("pedido_id"))
    elif nome == "registrar_avaliacao":
        r = loja.registrar_avaliacao(telefone, e["pedido_id"], int(e["nota"]), e.get("comentario"))
    elif nome == "registrar_pedido_oracao":
        r = loja.registrar_pedido_oracao(telefone, e["pedido"])
    elif nome == "chamar_humano":
        r = loja.pedir_humano(telefone, e["motivo"])
    else:
        raise ErroLoja(f"Ferramenta desconhecida: {nome}")
    return json.dumps(r, ensure_ascii=False)
