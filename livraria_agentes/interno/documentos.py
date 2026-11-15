"""Cópia de documentos dos e-mails para o arquivo da livraria.

Estrutura: ARQUIVO_DOCUMENTOS/AAAA-MM/remetente/arquivo (padrão: dados/estado/documentos).
Cada arquivo é identificado pelo conteúdo (SHA-256): o mesmo documento recebido duas
vezes é guardado uma vez só.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date
from email import message_from_bytes, policy
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

from .base import Base
from .email_imap import CaixaIMAP


def _seguro(nome: str, padrao: str = "arquivo") -> str:
    """Nome de arquivo sem caminhos, acentos problemáticos ou caracteres proibidos."""
    nome = Path(nome.replace("\\", "/")).name
    nome = unicodedata.normalize("NFKC", nome)
    nome = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nome).strip(" .")
    return (nome or padrao)[:150]


def copiar_documentos_email(caixa: CaixaIMAP, base: Base, pasta: Path, uid: str, incluir_email: bool) -> dict:
    bruto = caixa.bruto(uid)
    msg = message_from_bytes(bruto, policy=policy.default)
    remetente = parseaddr(str(msg["from"] or ""))[1] or "desconhecido"
    try:
        quando = parsedate_to_datetime(msg["date"]) if msg["date"] else None
    except (TypeError, ValueError):
        quando = None
    data_email = quando.isoformat(timespec="minutes") if quando else None
    destino = Path(pasta) / (quando or date.today()).strftime("%Y-%m") / _seguro(remetente, "desconhecido")

    arquivos = [(p.get_filename() or "anexo", p.get_content_type(), p.get_payload(decode=True) or b"")
                for p in msg.iter_attachments()]
    if incluir_email:
        assunto = _seguro(re.sub(r"[/\\]", "_", str(msg["subject"] or "sem assunto")))[:80]
        arquivos.append((f"email_{uid}_{assunto}.eml", "message/rfc822", bruto))

    copiados, repetidos = [], []
    for nome, tipo, dados in arquivos:
        if not dados:
            continue
        hash_ = hashlib.sha256(dados).hexdigest()
        existente = base.documento_existente(hash_)
        if existente:
            repetidos.append({"nome": nome, "ja_estava_em": existente["caminho"]})
            continue
        destino.mkdir(parents=True, exist_ok=True)
        caminho = destino / _seguro(nome)
        if caminho.exists():
            caminho = caminho.with_name(f"{caminho.stem}_{hash_[:8]}{caminho.suffix}")
        caminho.write_bytes(dados)
        doc_id = base.registrar_documento({
            "hash": hash_, "email_uid": uid, "remetente": remetente, "assunto": str(msg["subject"] or ""),
            "data_email": data_email, "nome": caminho.name, "tipo": tipo,
            "tamanho_kb": round(len(dados) / 1024, 1), "caminho": str(caminho)})
        copiados.append({"documento_id": doc_id, "nome": caminho.name, "caminho": str(caminho)})
    return {"email_uid": uid, "remetente": remetente, "copiados": copiados, "ja_existiam": repetidos}


def copiar_documentos_periodo(caixa: CaixaIMAP, base: Base, pasta: Path, desde: date, remetente: str | None,
                              assunto: str | None, maximo: int, incluir_email: bool) -> dict:
    resultados = [copiar_documentos_email(caixa, base, pasta, uid, incluir_email)
                  for uid in caixa.uids_desde(desde, remetente, assunto, maximo)]
    return {"emails_processados": len(resultados),
            "documentos_copiados": sum(len(r["copiados"]) for r in resultados),
            "ja_existiam": sum(len(r["ja_existiam"]) for r in resultados),
            "detalhes": [r for r in resultados if r["copiados"]][:30]}


def faturas_para_planilha(base: Base, arquivo: Path) -> dict:
    """Extrai a tabela de faturas registradas para uma planilha Excel."""
    from openpyxl import Workbook

    faturas = base.listar_faturas(False, None)
    livro = Workbook()
    aba = livro.active
    aba.title = "Faturas"
    colunas = ["id", "tipo", "emitente", "nif_emitente", "numero", "data_emissao", "vencimento", "valor", "moeda",
               "referencia", "erp", "documento_erp", "resumo", "email_uid"]
    aba.append(colunas)
    for f in faturas:
        aba.append([f.get(c) for c in colunas])
    Path(arquivo).parent.mkdir(parents=True, exist_ok=True)
    livro.save(arquivo)
    return {"ok": True, "arquivo": str(arquivo), "faturas": len(faturas)}
