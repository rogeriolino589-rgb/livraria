"""Exportação dos dados consolidados para o superapp.

Sempre gera um arquivo JSON em dados/estado/exportacoes/. Se SUPERAPP_URL estiver
configurada, também envia esse JSON por POST (com SUPERAPP_TOKEN no cabeçalho
Authorization, se existir). O formato é provisório até conhecermos a API do superapp.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path

import httpx

from .base import ERPS, Base

VERSAO_FORMATO = 1


def _dias(inicio: str, fim: str) -> int:
    return (date.fromisoformat(fim) - date.fromisoformat(inicio)).days


def montar(base: Base, inicio: str, fim: str) -> dict:
    return {
        "formato": VERSAO_FORMATO,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "periodo": {"inicio": inicio, "fim": fim},
        # Visão única 2016 até hoje: ERP19 até jul/2022, ERP22 a partir de ago/2022.
        "vendas": {
            agrupamento: base.resumo_vendas(inicio, fim, agrupamento, None)
            for agrupamento in (("dia" if _dias(inicio, fim) <= 92 else "mes"), "ano", "vendedor", "provincia")
        },
        "verificacao_historico": base.verificar_historico(inicio, fim),
        "faturas_email": [f for f in base.listar_faturas(False, None)
                          if f["data_emissao"] and inicio <= f["data_emissao"][:10] <= fim],
        "erps": list(ERPS),
    }


def exportar(base: Base, pasta: Path, inicio: str, fim: str, enviar: bool) -> dict:
    dados = montar(base, inicio, fim)
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"superapp_{inicio}_{fim}_{datetime.now():%Y%m%d%H%M%S}.json"
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    resultado = {"ok": True, "arquivo": str(arquivo), "enviado": False}
    url = os.environ.get("SUPERAPP_URL")
    if enviar:
        if not url:
            resultado["aviso"] = "SUPERAPP_URL não configurada: o arquivo foi gerado, mas não enviado."
        else:
            cabecalhos = {}
            if os.environ.get("SUPERAPP_TOKEN"):
                cabecalhos["Authorization"] = f"Bearer {os.environ['SUPERAPP_TOKEN']}"
            resp = httpx.post(url, json=dados, headers=cabecalhos, timeout=30)
            resultado["enviado"] = resp.is_success
            resultado["resposta_superapp"] = f"{resp.status_code}: {resp.text[:300]}"
    with base.db:
        base.db.execute("INSERT INTO exportacoes (inicio, fim, arquivo, enviado, em) VALUES (?,?,?,?,?)",
                        (inicio, fim, str(arquivo), int(resultado["enviado"]), dados["gerado_em"]))
    return resultado
