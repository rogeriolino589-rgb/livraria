"""Vendedores de cada linha de WhatsApp e avisos para eles.

Cada linha (ex.: igrejas, empresas/instituições/livrarias/revendedores, retalho) tem um vendedor. Quando o
robô passa um cliente para uma pessoa, ou quando entra um pedido, o vendedor da linha desse cliente recebe
um aviso no WhatsApp pessoal e uma tarefa em seu nome.

Configuração em config/vendedores.json (fora do Git, porque tem números pessoais), por número da linha:

    {"+258 86 504 8400": {"nome": "Maria", "whatsapp": "258840000001"}}

A linha de cada tipo de cliente vem de `contactos_por_tipo` no perfil do país.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Callable

from .pais import PAIS, _achar

log = logging.getLogger(__name__)


def carregar(arquivo: Path | None = None) -> dict[str, dict]:
    caminho = Path(arquivo or os.environ.get("VENDEDORES_ARQUIVO", _achar("config/vendedores.json")))
    if not caminho.exists():
        return {}
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return {linha: v for linha, v in dados.items() if not linha.startswith("_") and v.get("whatsapp")}


def linha_do_tipo(tipo: str | None) -> str | None:
    """Número da linha de atendimento de um tipo de cliente (quem não está no cadastro vai para 'sem cadastro')."""
    procurado = tipo or "sem cadastro"
    for linha, tipos in PAIS.contactos_por_tipo.items():
        if procurado in tipos:
            return linha
    return None


# Modelo aprovado pela Meta (categoria Utilidade, pt_PT) para quando o vendedor não falou com o número da
# loja nas últimas 24h e a mensagem livre não pode ser entregue.
MODELO_AVISO = "Olá, {{1}}! {{2}}: {{3}} ({{4}}). Os detalhes estão na sua lista de tarefas; responda aqui para ver."


class Avisos:
    """Envia avisos aos vendedores. `enviar(whatsapp, texto)` é o canal (WhatsApp ou terminal);
    `enviar_modelo(whatsapp, modelo, parametros, texto)` é usado se a mensagem livre não puder ser entregue."""

    def __init__(self, enviar: Callable[[str, str], None], vendedores: dict[str, dict] | None = None,
                 enviar_modelo: Callable[[str, str, list[str], str], None] | None = None):
        self.enviar = enviar
        self.enviar_modelo = enviar_modelo
        self.vendedores = carregar() if vendedores is None else vendedores

    def vendedor_do_cliente(self, tipo: str | None) -> tuple[str, dict] | tuple[None, None]:
        linha = linha_do_tipo(tipo)
        if linha and linha in self.vendedores:
            return linha, self.vendedores[linha]
        return None, None

    def avisar(self, loja, telefone_cliente: str, assunto: str, detalhe: str) -> dict | None:
        ficha = loja.ficha_cliente(telefone_cliente)
        linha, vendedor = self.vendedor_do_cliente(ficha.get("tipo"))
        if not vendedor:
            return None
        nome_cliente = ficha.get("nome", "cliente sem nome registado")
        texto = (f"🔔 {assunto}\n"
                 f"Cliente: {nome_cliente} ({ficha.get('tipo', 'sem cadastro')})\n"
                 f"WhatsApp: +{telefone_cliente} · https://wa.me/{telefone_cliente}\n"
                 f"{detalhe}\n"
                 f"(linha {linha})")
        tarefa = loja.criar_tarefa(f"{assunto}: {nome_cliente} (+{telefone_cliente}). {detalhe}",
                                   vendedor["nome"], loja.relogio().date().isoformat())
        try:
            self.enviar(vendedor["whatsapp"], texto)
            enviado = True
        except Exception:  # fora da janela de 24h do WhatsApp, sem internet...
            enviado = False
            if self.enviar_modelo:
                parametros = [vendedor["nome"].split()[0], assunto, nome_cliente, f"+{telefone_cliente}"]
                try:
                    self.enviar_modelo(vendedor["whatsapp"], "aviso_vendedor", parametros,
                                       re.sub(r"\{\{(\d+)\}\}", lambda m: parametros[int(m.group(1)) - 1], MODELO_AVISO))
                    enviado = True
                except Exception:
                    log.exception("Não consegui avisar o vendedor %s nem por modelo", vendedor["nome"])
            else:
                log.exception("Não consegui avisar o vendedor %s", vendedor["nome"])
        return {"vendedor": vendedor["nome"], "linha": linha, "enviado": enviado, "tarefa_id": tarefa["id"]}
