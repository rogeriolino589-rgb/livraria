"""Perfil do país onde o robô está a funcionar.

Cada loja (Moçambique, Eswatini, África do Sul, RDC...) roda a sua própria instalação, com os seus dados,
e escolhe o perfil com a variável LIVRARIA_PAIS (padrão: mz). Os perfis ficam em config/paises/<codigo>.json:
moeda, fuso horário, línguas, indicativo telefónico, formas de pagamento, taxa de entrega, imposto e a
identificação fiscal. Para abrir um país novo, copie um perfil, ajuste os valores e confirme-os com a equipa local.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

PASTA_PAISES = Path(__file__).resolve().parent.parent / "config" / "paises"


@dataclass(frozen=True)
class Pais:
    codigo: str
    nome: str
    nome_loja: str
    moeda: str  # código ISO, ex.: MZN
    simbolo: str  # como aparece nos preços, ex.: MT
    simbolo_antes: bool  # "R 1 250,00" (antes) ou "1.250,00 MT" (depois)
    separador_milhar: str
    separador_decimal: str
    fuso: str
    lingua_clientes: str  # pt, en ou fr: língua das mensagens fixas e padrão das respostas
    descricao_lingua: str  # instrução para os agentes, ex.: "português de Moçambique (norma europeia)"
    linguas_locais: list[str]
    lingua_equipa: str
    idioma_modelos_whatsapp: str  # ex.: pt_PT, en, fr
    indicativo: str  # ex.: 258
    digitos_nacionais: int  # dígitos do número sem o indicativo
    prefixos_moveis: list[str]  # começos dos números de telemóvel (sem o 0 inicial)
    formas_pagamento: list[str]
    taxa_entrega: float
    imposto_nome: str
    imposto_taxa: float
    id_fiscal: str  # NUIT, TIN, NIF...
    desconto_minimo: float | None = None  # compra mínima (moeda local) para o desconto de instituições
    observacoes: list[str] = field(default_factory=list)

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.fuso)

    def dinheiro(self, valor: float, com_simbolo: bool = False) -> str:
        """1234.5 -> '1.234,50' (ou '1 234,50' / '1,234.50', conforme o país)."""
        texto = f"{valor:,.2f}".replace(",", "\0").replace(".", self.separador_decimal).replace(
            "\0", self.separador_milhar)
        if not com_simbolo:
            return texto
        return f"{self.simbolo} {texto}" if self.simbolo_antes else f"{texto} {self.simbolo}"

    def numeros_whatsapp(self, telefone: str) -> list[str]:
        """Converte números do cadastro para o formato do WhatsApp (indicativo + número, só dígitos)."""
        bruto = str(telefone or "")
        digitos = re.sub(r"\D", "", bruto)
        n, ind = self.digitos_nacionais, self.indicativo
        if len(digitos) == len(ind) + n and digitos.startswith(ind):
            return [digitos] if self._movel(digitos[len(ind):]) else []
        if len(digitos) == n + 1 and digitos.startswith("0"):
            digitos = digitos[1:]
        if len(digitos) == n and self._movel(digitos):
            return [ind + digitos]
        if len(digitos) == 2 * n:  # dois números juntos
            return [x for parte in (digitos[:n], digitos[n:]) for x in self.numeros_whatsapp(parte)]
        partes = [p for p in re.split(r"[/,;]| e | and | et ", bruto) if p.strip()]
        if len(partes) > 1:
            return [x for p in partes for x in self.numeros_whatsapp(p)]
        return []

    def _movel(self, nacional: str) -> bool:
        return not self.prefixos_moveis or nacional.startswith(tuple(self.prefixos_moveis))


def carregar(codigo: str | None = None) -> Pais:
    codigo = (codigo or os.environ.get("LIVRARIA_PAIS", "mz")).lower()
    arquivo = PASTA_PAISES / f"{codigo}.json"
    if not arquivo.exists():
        disponiveis = ", ".join(sorted(p.stem for p in PASTA_PAISES.glob("*.json")))
        raise SystemExit(f"País '{codigo}' sem perfil em {PASTA_PAISES}. Disponíveis: {disponiveis}")
    dados = {k: v for k, v in json.loads(arquivo.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    if os.environ.get("LOJA_NOME"):
        dados["nome_loja"] = os.environ["LOJA_NOME"]
    if os.environ.get("LIVRARIA_FUSO"):
        dados["fuso"] = os.environ["LIVRARIA_FUSO"]
    return Pais(codigo=codigo, **dados)


PAIS = carregar()
