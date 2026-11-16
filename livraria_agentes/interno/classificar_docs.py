"""Reconhecimento dos documentos que chegam por e-mail à CPAD Moçambique (sem IA, com regras testáveis).

    classificar(assunto, remetente, anexos, texto) -> {"tipo", "motivo", "guardar"}
    extracto_conta_corrente(texto)                 -> lançamentos, saldo e documentos em aberto

Tipos: fatura_fornecedor, extracto_fornecedor, bordero_pagamento, recibo, comprovativo_carteira,
relatorio_vendas, publicidade, outro. "guardar" diz se os anexos devem ir para o arquivo de documentos.
Os originais nunca são alterados: estas funções só leem texto.
"""

from __future__ import annotations

import re
import unicodedata

TIPOS = ("fatura_fornecedor", "extracto_fornecedor", "bordero_pagamento", "recibo", "comprovativo_carteira",
         "relatorio_vendas", "publicidade", "outro")


def _sem_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto or "") if not unicodedata.combining(c)).lower()


# Ordem importa: o primeiro que bate decide.
REGRAS: list[tuple[str, str, str]] = [
    # (tipo, onde procurar: "assunto" | "anexo" | "texto" | "tudo", expressão)
    ("relatorio_vendas", "assunto", r"\bvendas cpad\b|\bfaturamento\b.*\bfilial\b"),
    ("relatorio_vendas", "anexo", r"faturamento\s*-\s*filial"),
    ("extracto_fornecedor", "tudo", r"\bextracto de conta\b|\bextrato de conta\b|\bconta corrente\b"),
    ("bordero_pagamento", "tudo", r"\bbordero|\btransferencias?_entre_contas|\bordem de pagamento\b"
                                  r"|\bregistamos a operacao\b"),
    ("comprovativo_carteira", "tudo", r"\bpagar com o m-?pesa\b|\bm-?pesa\b.*\b(confirmad|recibo|transac)"
                                      r"|\be-?mola\b.*\bconfirmad|\bmkesh\b.*\bconfirmad"),
    ("recibo", "tudo", r"\brecibo\b|\breceipt\b|\bREC \d{6,}"),
    ("fatura_fornecedor", "tudo", r"\bfactura|\bfatura|\binvoice\b|\bFT \d|\bFCC \d"),
]

PUBLICIDADE = re.compile(r"\bclique aqui\b|\bao vivo\b|\bfaltam menos de\b|\bcurso gratuito\b|\bblack\b"
                         r"|\binscricao\b|\bnewsletter\b|\bdescadastr|\bunsubscribe\b|\bpromoc")


def classificar(assunto: str, remetente: str, anexos: list[str] | None = None, texto: str = "") -> dict:
    anexos = anexos or []
    campos = {"assunto": _sem_acentos(assunto), "anexo": _sem_acentos(" ".join(anexos)),
              "texto": _sem_acentos(texto)}
    campos["tudo"] = " ".join(campos.values())
    # Publicidade primeiro: "faturar 10 mil por mês" num e-mail de curso não é fatura.
    if PUBLICIDADE.search(campos["assunto"] + " " + campos["texto"][:600]) and not anexos:
        return {"tipo": "publicidade", "motivo": "texto promocional sem anexos", "guardar": False}
    for tipo, onde, expressao in REGRAS:
        achado = re.search(expressao, campos[onde], re.IGNORECASE)
        if achado:
            # Uma palavra-chave só no corpo, sem anexo nenhum, é conversa sobre o documento, não o documento.
            guardar = bool(anexos) or tipo == "comprovativo_carteira"
            return {"tipo": tipo, "motivo": f"'{achado.group(0)}' em {onde}", "guardar": guardar}
    return {"tipo": "outro", "motivo": "nenhuma regra", "guardar": False}


# --- Extracto de conta corrente de fornecedor (ex.: "Conta Corrente CPAD Livraria - Moçambique") ---

_NUMERO = r"(?:-?\d{1,3}(?:[.,]\d{3})+[.,]\d{2}|-?\d+[.,]\d{2})"  # 1.234,50 | 1,234.50 | 23922.50
_LANCAMENTO = re.compile(
    rf"(?P<data>\d{{4}}-\d{{2}}-\d{{2}})\s+(?P<tipo>[A-Za-zÀ-ú][A-Za-zÀ-ú ./]+?)\s+"
    rf"(?P<doc>[A-Z]{{2,4}}\s?\d{{4,}})\s+(?P<valor>{_NUMERO})\s+(?P<saldo>{_NUMERO})")
_SALDO_INICIAL = re.compile(rf"Saldo Inicial\s+(?:{_NUMERO}\s+{_NUMERO}\s+)?(?P<saldo>{_NUMERO})", re.I)


def _valor(texto: str) -> float:
    texto = texto.replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".") if texto.rfind(",") > texto.rfind(".") else texto.replace(",", "")
    return float(texto.replace(",", "."))


def extracto_conta_corrente(texto: str) -> dict:
    """Lê o extracto (texto do PDF) e diz o que está em aberto.

    O saldo de cada linha decide se o valor é débito (fatura: o saldo sobe) ou crédito (recibo: desce).
    As faturas em aberto são as mais recentes cuja soma dá o saldo final (os recibos pagam as mais antigas).
    """
    inicial = _SALDO_INICIAL.search(texto)
    saldo = _valor(inicial.group("saldo")) if inicial else 0.0
    saldo_inicial = saldo
    lancamentos, avisos = [], []
    for m in _LANCAMENTO.finditer(texto):
        valor, novo = _valor(m.group("valor")), _valor(m.group("saldo"))
        if abs(saldo + valor - novo) < 0.01:
            natureza = "debito"
        elif abs(saldo - valor - novo) < 0.01:
            natureza = "credito"
        else:
            natureza = "?"
            avisos.append(f"{m.group('doc')}: o saldo {novo:.2f} não bate com {saldo:.2f} ± {valor:.2f}")
        lancamentos.append({"data": m.group("data"), "tipo": m.group("tipo").strip(), "documento": m.group("doc"),
                            "valor": valor, "natureza": natureza, "saldo": novo})
        saldo = novo
    em_aberto, falta = [], round(saldo, 2)
    for lanc in reversed([x for x in lancamentos if x["natureza"] == "debito"]):
        if falta <= 0.005:
            break
        parte = min(lanc["valor"], falta)
        em_aberto.append({**lanc, "em_aberto": round(parte, 2), "parcial": parte < lanc["valor"]})
        falta = round(falta - parte, 2)
    em_aberto.reverse()
    return {"saldo_inicial": saldo_inicial, "saldo_final": round(saldo, 2), "lancamentos": lancamentos,
            "em_aberto": em_aberto, "total_faturas": round(sum(x["valor"] for x in lancamentos
                                                               if x["natureza"] == "debito"), 2),
            "total_pago": round(sum(x["valor"] for x in lancamentos if x["natureza"] == "credito"), 2),
            "avisos": avisos}
