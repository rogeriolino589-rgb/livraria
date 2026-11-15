"""Leitura de e-mails por IMAP e cópia dos documentos anexados.

A caixa é aberta em modo `readonly` e as mensagens são baixadas com BODY.PEEK:
os documentos são extraídos e copiados para o arquivo da livraria (veja
documentos.py), mas nada é apagado, movido ou marcado como lido na caixa, e o
assistente não envia e-mails.

Variáveis de ambiente: IMAP_HOST, IMAP_PORTA (993), IMAP_USUARIO, IMAP_SENHA, IMAP_PASTA (INBOX).
"""

from __future__ import annotations

import imaplib
import io
import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

log = logging.getLogger(__name__)

LIMITE_CORPO = 15000
LIMITE_ANEXO = 15000
MESES_IMAP = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@dataclass
class ConfigIMAP:
    host: str
    usuario: str
    senha: str
    porta: int = 993
    pasta: str = "INBOX"

    @classmethod
    def do_ambiente(cls) -> ConfigIMAP | None:
        if not all(os.environ.get(v) for v in ("IMAP_HOST", "IMAP_USUARIO", "IMAP_SENHA")):
            return None
        return cls(os.environ["IMAP_HOST"], os.environ["IMAP_USUARIO"], os.environ["IMAP_SENHA"],
                   int(os.environ.get("IMAP_PORTA", "993")), os.environ.get("IMAP_PASTA", "INBOX"))


def _ascii(texto: str) -> str:
    """A busca IMAP sem CHARSET só aceita ASCII: tira acentos e aspas."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.replace('"', "").strip()


def _texto_pdf(dados: bytes) -> str:
    try:
        from pypdf import PdfReader

        leitor = PdfReader(io.BytesIO(dados))
        return "\n".join((pagina.extract_text() or "") for pagina in leitor.pages[:20])
    except Exception as erro:  # PDF protegido, corrompido ou escaneado
        return f"(não consegui ler o PDF: {erro})"


def _texto_planilha(dados: bytes) -> str:
    try:
        from openpyxl import load_workbook

        livro = load_workbook(io.BytesIO(dados), read_only=True, data_only=True)
        linhas = []
        for aba in livro.worksheets:
            linhas.append(f"[aba {aba.title}]")
            for i, linha in enumerate(aba.iter_rows(values_only=True)):
                if i >= 200:
                    linhas.append("...")
                    break
                linhas.append(";".join("" if c is None else str(c) for c in linha))
        return "\n".join(linhas)
    except Exception as erro:
        return f"(não consegui ler a planilha: {erro})"


def _texto_anexo(nome: str, tipo: str, dados: bytes) -> str:
    nome_min = nome.lower()
    if tipo == "application/pdf" or nome_min.endswith(".pdf"):
        texto = _texto_pdf(dados)
    elif nome_min.endswith((".xlsx", ".xlsm")):
        texto = _texto_planilha(dados)
    elif tipo.startswith("text/") or nome_min.endswith((".xml", ".csv", ".txt", ".json")):
        texto = dados.decode("utf-8", errors="replace")
    else:
        return "(tipo de anexo não lido)"
    return texto[:LIMITE_ANEXO]


def _corpo(msg: EmailMessage) -> str:
    parte = msg.get_body(preferencelist=("plain", "html"))
    if parte is None:
        return ""
    texto = parte.get_content()
    if parte.get_content_subtype() == "html":
        texto = re.sub(r"(?is)<(script|style).*?</\1>", " ", texto)
        texto = re.sub(r"(?s)<[^>]+>", " ", texto)
        texto = re.sub(r"&nbsp;", " ", texto)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", texto)).strip()


def analisar(uid: str, bruto: bytes, com_conteudo: bool) -> dict:
    msg = message_from_bytes(bruto, policy=policy.default)
    try:
        data = parsedate_to_datetime(msg["date"]).isoformat(timespec="minutes") if msg["date"] else None
    except (TypeError, ValueError):
        data = None
    anexos = []
    for parte in msg.iter_attachments():
        nome = parte.get_filename() or "sem_nome"
        dados = parte.get_payload(decode=True) or b""
        anexo = {"nome": nome, "tipo": parte.get_content_type(), "tamanho_kb": round(len(dados) / 1024, 1)}
        if com_conteudo:
            anexo["texto"] = _texto_anexo(nome, parte.get_content_type(), dados)
        anexos.append(anexo)
    email = {"uid": uid, "de": str(msg["from"] or ""), "para": str(msg["to"] or ""),
             "assunto": str(msg["subject"] or ""), "data": data, "anexos": anexos}
    corpo = _corpo(msg)
    if com_conteudo:
        email["corpo"] = corpo[:LIMITE_CORPO]
    else:
        email["previa"] = corpo[:300]
    return email


class CaixaIMAP:
    def __init__(self, config: ConfigIMAP, conectar=imaplib.IMAP4_SSL):
        self.config = config
        self._conectar = conectar

    def _abrir(self):
        conexao = self._conectar(self.config.host, self.config.porta)
        conexao.login(self.config.usuario, self.config.senha)
        estado, _ = conexao.select(self.config.pasta, readonly=True)
        if estado != "OK":
            raise RuntimeError(f"Não consegui abrir a pasta {self.config.pasta}")
        return conexao

    def listar(self, desde: date, remetente: str | None = None, assunto: str | None = None,
               maximo: int = 30) -> list[dict]:
        """E-mails a partir de uma data (mais recentes primeiro), só cabeçalho e prévia."""
        criterios = ["SINCE", f"{desde.day:02d}-{MESES_IMAP[desde.month - 1]}-{desde.year}"]
        if remetente:
            criterios += ["FROM", f'"{_ascii(remetente)}"']
        if assunto:
            criterios += ["SUBJECT", f'"{_ascii(assunto)}"']
        conexao = self._abrir()
        try:
            estado, dados = conexao.uid("SEARCH", *criterios)
            if estado != "OK":
                raise RuntimeError("A busca IMAP falhou")
            uids = dados[0].split()[::-1][:maximo]
            return [self._baixar(conexao, uid.decode(), com_conteudo=False) for uid in uids]
        finally:
            self._fechar(conexao)

    def ler(self, uid: str) -> dict:
        """Um e-mail completo, com o texto dos anexos (PDF, planilhas, XML, CSV)."""
        if not uid.isdigit():
            raise ValueError("uid inválido")
        conexao = self._abrir()
        try:
            return self._baixar(conexao, uid, com_conteudo=True)
        finally:
            self._fechar(conexao)

    def bruto(self, uid: str) -> bytes:
        """O e-mail original completo (.eml), para copiar documentos e anexos."""
        if not uid.isdigit():
            raise ValueError("uid inválido")
        conexao = self._abrir()
        try:
            estado, dados = conexao.uid("FETCH", uid, "(BODY.PEEK[])")
            if estado != "OK" or not dados or not isinstance(dados[0], tuple):
                raise RuntimeError(f"Não encontrei o e-mail {uid}")
            return dados[0][1]
        finally:
            self._fechar(conexao)

    def uids_desde(self, desde: date, remetente: str | None, assunto: str | None, maximo: int) -> list[str]:
        criterios = ["SINCE", f"{desde.day:02d}-{MESES_IMAP[desde.month - 1]}-{desde.year}"]
        if remetente:
            criterios += ["FROM", f'"{_ascii(remetente)}"']
        if assunto:
            criterios += ["SUBJECT", f'"{_ascii(assunto)}"']
        conexao = self._abrir()
        try:
            estado, dados = conexao.uid("SEARCH", *criterios)
            if estado != "OK":
                raise RuntimeError("A busca IMAP falhou")
            return [u.decode() for u in dados[0].split()[::-1][:maximo]]
        finally:
            self._fechar(conexao)

    def _baixar(self, conexao, uid: str, com_conteudo: bool) -> dict:
        estado, dados = conexao.uid("FETCH", uid, "(BODY.PEEK[])")
        if estado != "OK" or not dados or not isinstance(dados[0], tuple):
            raise RuntimeError(f"Não encontrei o e-mail {uid}")
        return analisar(uid, dados[0][1], com_conteudo)

    @staticmethod
    def _fechar(conexao) -> None:
        try:
            conexao.logout()
        except Exception:
            log.debug("Falha ao fechar a conexão IMAP", exc_info=True)
