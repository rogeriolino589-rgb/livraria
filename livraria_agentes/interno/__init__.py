"""Assistente interno da equipe da livraria."""

from __future__ import annotations

import os
from pathlib import Path

from ..config import PASTA_ESTADO
from ..loja import Loja
from .assistente import Assistente
from .base import Base
from .email_imap import CaixaIMAP, ConfigIMAP
from .ferramentas import Contexto

RAIZ = Path(__file__).resolve().parent.parent.parent
PASTA_ENTRADA = Path(os.environ.get("ERP_PASTA_ENTRADA", RAIZ / "dados" / "entrada"))
PASTA_DOCUMENTOS = Path(os.environ.get("ARQUIVO_DOCUMENTOS", PASTA_ESTADO / "documentos"))


def equipe_whatsapp() -> dict[str, str]:
    """EQUIPE_WHATSAPP="244923000001:Rogério,244923000002:Ana" -> {telefone: nome}."""
    equipe = {}
    for item in os.environ.get("EQUIPE_WHATSAPP", "").split(","):
        telefone, _, nome = item.strip().partition(":")
        telefone = "".join(c for c in telefone if c.isdigit())
        if telefone:
            equipe[telefone] = nome.strip() or telefone
    return equipe


def abrir_assistente(loja: Loja) -> Assistente:
    config_imap = ConfigIMAP.do_ambiente()
    ctx = Contexto(loja, Base(PASTA_ESTADO / "interno.db", RAIZ / "config" / "erps.json"),
                   CaixaIMAP(config_imap) if config_imap else None, PASTA_ENTRADA, PASTA_ESTADO / "exportacoes",
                   PASTA_DOCUMENTOS)
    return Assistente(ctx, PASTA_ESTADO / "conversas_equipe")
