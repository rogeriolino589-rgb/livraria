"""Onde ficam os dados em uso (catálogo, pedidos, conversas)."""

from __future__ import annotations

import os
from pathlib import Path

from .loja import Loja
from .motor import Motor

PASTA_ESTADO = Path(os.environ.get("LIVRARIA_DADOS", Path(__file__).resolve().parent.parent / "dados" / "estado"))


def abrir() -> tuple[Loja, Motor]:
    loja = Loja(PASTA_ESTADO / "loja.json")
    return loja, Motor(loja, PASTA_ESTADO / "conversas")
