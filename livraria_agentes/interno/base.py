"""Base de dados interna (SQLite): vendas importadas dos ERPs, faturas encontradas nos
e-mails, rascunhos de posts e exportações para o superapp.

Os ERPs (ERP19 e ERP22) entram por relatórios exportados (planilha .xlsx ou .csv).
As colunas são reconhecidas pelo nome; se o relatório usar outros nomes, ajuste
`config/erps.json` (veja `config/erps.exemplo.json`).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

ERPS = ("erp19", "erp22")
CAMPOS = ("documento", "data", "vendedor", "provincia", "cliente", "valor")
OBRIGATORIOS = ("documento", "data", "valor")

# Nomes de coluna aceitos para cada campo (comparados sem acentos, espaços ou pontuação).
SINONIMOS = {
    "documento": ["documento", "doc", "nodocumento", "numerodocumento", "numdoc", "ndoc", "nºdoc", "fatura",
                  "factura", "numerofatura", "numerofactura", "nfatura", "recibo", "numero", "nº"],
    "data": ["data", "datadocumento", "dataemissao", "emissao", "datavenda", "dt", "datahora"],
    "vendedor": ["vendedor", "operador", "utilizador", "usuario", "funcionario", "atendente", "colaborador"],
    "provincia": ["provincia", "regiao", "estado", "loja", "filial", "localidade", "cidade", "municipio"],
    "cliente": ["cliente", "nomecliente", "comprador", "entidade"],
    "valor": ["valor", "total", "valortotal", "montante", "totaldocumento", "valorliquido", "totalliquido",
              "totalcomiva", "liquido"],
}
AGRUPAMENTOS = {"vendedor": "vendedor", "provincia": "provincia", "dia": "data", "erp": "erp",
                "mes": "substr(data, 1, 7)", "cliente": "cliente"}

ESQUEMA = """
CREATE TABLE IF NOT EXISTS vendas (
    erp TEXT NOT NULL, documento TEXT NOT NULL, data TEXT NOT NULL, vendedor TEXT, provincia TEXT,
    cliente TEXT, valor REAL NOT NULL, arquivo TEXT, linha INTEGER);
CREATE INDEX IF NOT EXISTS vendas_erp_data ON vendas (erp, data);
CREATE INDEX IF NOT EXISTS vendas_doc ON vendas (documento);
CREATE TABLE IF NOT EXISTS importacoes (
    hash TEXT PRIMARY KEY, erp TEXT, arquivo TEXT, linhas INTEGER, inicio TEXT, fim TEXT, em TEXT);
CREATE TABLE IF NOT EXISTS faturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT, email_uid TEXT, tipo TEXT, emitente TEXT, nif_emitente TEXT,
    numero TEXT, data_emissao TEXT, vencimento TEXT, valor REAL, moeda TEXT, referencia TEXT,
    resumo TEXT, documento_erp TEXT, erp TEXT, registrado_em TEXT,
    UNIQUE (email_uid, numero));
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, rede TEXT, texto TEXT, sugestao_imagem TEXT, status TEXT,
    criado_em TEXT);
CREATE TABLE IF NOT EXISTS exportacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, inicio TEXT, fim TEXT, arquivo TEXT, enviado INTEGER, em TEXT);
"""


class ErroDados(Exception):
    pass


def _chave(texto: object) -> str:
    sem_acento = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9º]", "", sem_acento.lower())


def normalizar_documento(doc: object) -> str:
    """'FT 2026/00123' e 'ft2026/123' viram a mesma chave para cruzar os ERPs."""
    texto = str(doc or "").strip().upper()
    if isinstance(doc, float) and doc.is_integer():
        texto = str(int(doc))
    partes = re.findall(r"[A-Z]+|\d+", texto)
    return "".join(p.lstrip("0") or "0" if p.isdigit() else p for p in partes)


def ler_data(valor: object) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor or "").strip()
    if not texto:
        return None
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(texto.split()[0].split("T")[0], formato).date()
        except ValueError:
            continue
    return None


def ler_valor(valor: object) -> float | None:
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = re.sub(r"[^\d,.\-]", "", str(valor or ""))
    if not texto or texto in "-.,":
        return None
    if "," in texto and "." in texto:
        # o separador que aparece por último é o decimal
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        inteiro, _, decimal = texto.rpartition(",")
        texto = texto.replace(",", ".") if len(decimal) != 3 else inteiro.replace(",", "") + decimal
    elif texto.count(".") > 1 or re.fullmatch(r"-?\d{1,3}\.\d{3}", texto):
        texto = texto.replace(".", "")  # "12.345" em português é doze mil
    try:
        return float(texto)
    except ValueError:
        return None


class _PontoEVirgula(csv.excel):
    delimiter = ";"


def _linhas_arquivo(caminho: Path) -> list[list]:
    if caminho.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook

        livro = load_workbook(caminho, read_only=True, data_only=True)
        aba = max(livro.worksheets, key=lambda a: a.max_row or 0)
        return [list(linha) for linha in aba.iter_rows(values_only=True)]
    if caminho.suffix.lower() in (".csv", ".txt"):
        bruto = caminho.read_bytes()
        for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                texto = bruto.decode(codificacao)
                break
            except UnicodeDecodeError:
                continue
        try:
            dialeto = csv.Sniffer().sniff(texto[:5000], delimiters=";,\t|")
        except csv.Error:
            dialeto = _PontoEVirgula
        return [linha for linha in csv.reader(io.StringIO(texto), dialeto)]
    raise ErroDados(f"Formato não suportado: {caminho.suffix} (use .xlsx ou .csv)")


def _mapear_colunas(linhas: list[list], forcadas: dict[str, str]) -> tuple[int, dict[str, int]]:
    """Acha a linha de cabeçalho (entre as 30 primeiras) e a coluna de cada campo."""
    melhor = (-1, -1, {})
    forcadas_chave = {campo: _chave(nome) for campo, nome in forcadas.items()}
    for i, linha in enumerate(linhas[:30]):
        cabecalho = [_chave(c) for c in linha]
        mapa: dict[str, int] = {}
        for campo in CAMPOS:
            opcoes = [forcadas_chave[campo]] if campo in forcadas_chave else SINONIMOS[campo]
            for opcao in opcoes:
                if opcao in cabecalho and cabecalho.index(opcao) not in mapa.values():
                    mapa[campo] = cabecalho.index(opcao)
                    break
        pontos = sum(1 for c in OBRIGATORIOS if c in mapa) * 10 + len(mapa)
        if pontos > melhor[0]:
            melhor = (pontos, i, mapa)
    _, linha_cab, mapa = melhor
    faltando = [c for c in OBRIGATORIOS if c not in mapa]
    if faltando:
        raise ErroDados(f"Não reconheci as colunas {', '.join(faltando)}. "
                        "Configure os nomes em config/erps.json.")
    return linha_cab, mapa


class Base:
    def __init__(self, arquivo: Path, config_erps: Path | None = None):
        self.arquivo = Path(arquivo)
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.arquivo, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(ESQUEMA)
        self.config = {}
        if config_erps and Path(config_erps).exists():
            self.config = json.loads(Path(config_erps).read_text(encoding="utf-8"))

    def _q(self, sql: str, args: tuple = ()) -> list[dict]:
        return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    # ------------------------------------------------------------ importação
    def importar_relatorio(self, caminho: Path, erp: str) -> dict:
        erp = erp.lower()
        if erp not in ERPS:
            raise ErroDados(f"ERP desconhecido: {erp}. Use {' ou '.join(ERPS)}.")
        caminho = Path(caminho)
        conteudo = caminho.read_bytes()
        hash_ = hashlib.sha256(conteudo).hexdigest()
        if self._q("SELECT 1 FROM importacoes WHERE hash = ?", (hash_,)):
            return {"ok": True, "aviso": "Este arquivo já tinha sido importado.", "arquivo": caminho.name}
        linhas = _linhas_arquivo(caminho)
        linha_cab, mapa = _mapear_colunas(linhas, self.config.get(erp, {}).get("colunas", {}))
        registros, ignoradas = [], 0
        for n, linha in enumerate(linhas[linha_cab + 1:], start=linha_cab + 2):
            celula = lambda campo: linha[mapa[campo]] if campo in mapa and mapa[campo] < len(linha) else None
            documento, data_, valor = celula("documento"), ler_data(celula("data")), ler_valor(celula("valor"))
            if not documento or data_ is None or valor is None:
                ignoradas += 1  # linhas de total, subtítulos, em branco
                continue
            if re.search(r"(?i)total", str(documento)):
                ignoradas += 1
                continue
            registros.append((erp, normalizar_documento(documento), data_.isoformat(),
                              str(celula("vendedor") or "").strip() or None,
                              str(celula("provincia") or "").strip() or None,
                              str(celula("cliente") or "").strip() or None, valor, caminho.name, n))
        if not registros:
            raise ErroDados("Nenhuma linha de venda válida no arquivo.")
        inicio = min(r[2] for r in registros)
        fim = max(r[2] for r in registros)
        with self.db:
            # A exportação mais nova manda: substitui o que havia do mesmo ERP nesse período.
            apagadas = self.db.execute("DELETE FROM vendas WHERE erp = ? AND data BETWEEN ? AND ?",
                                       (erp, inicio, fim)).rowcount
            self.db.executemany("INSERT INTO vendas VALUES (?,?,?,?,?,?,?,?,?)", registros)
            self.db.execute("INSERT INTO importacoes VALUES (?,?,?,?,?,?,?)",
                            (hash_, erp, caminho.name, len(registros), inicio, fim,
                             datetime.now().isoformat(timespec="minutes")))
        colunas = {campo: str(linhas[linha_cab][i]) for campo, i in mapa.items()}
        return {"ok": True, "erp": erp, "arquivo": caminho.name, "linhas_importadas": len(registros),
                "linhas_ignoradas": ignoradas, "substituidas": apagadas, "periodo": [inicio, fim],
                "colunas_reconhecidas": colunas}

    def importar_pasta(self, pasta: Path) -> list[dict]:
        """Importa os relatórios novos de pasta/erp19 e pasta/erp22."""
        resultados = []
        for erp in ERPS:
            for arq in sorted((Path(pasta) / erp).glob("*")):
                if arq.suffix.lower() in (".xlsx", ".xlsm", ".csv"):
                    try:
                        resultados.append(self.importar_relatorio(arq, erp))
                    except ErroDados as erro:
                        resultados.append({"ok": False, "erp": erp, "arquivo": arq.name, "erro": str(erro)})
        return resultados

    # ---------------------------------------------------------------- análises
    def _docs(self, inicio: str, fim: str, erp: str | None = None) -> str:
        """Subconsulta com um registro por documento (soma as linhas de itens do mesmo documento)."""
        filtro = "AND erp = ?" if erp else ""
        return (f"(SELECT erp, documento, MIN(data) AS data, MAX(vendedor) AS vendedor, "
                f"MAX(provincia) AS provincia, MAX(cliente) AS cliente, ROUND(SUM(valor), 2) AS valor "
                f"FROM vendas WHERE data BETWEEN ? AND ? {filtro} GROUP BY erp, documento)")

    def resumo_vendas(self, inicio: str, fim: str, agrupar_por: str, erp: str | None) -> list[dict]:
        if agrupar_por not in AGRUPAMENTOS:
            raise ErroDados(f"Agrupe por: {', '.join(AGRUPAMENTOS)}.")
        expr = AGRUPAMENTOS[agrupar_por]
        args = (inicio, fim, erp) if erp else (inicio, fim)
        return self._q(
            f"SELECT COALESCE({expr}, '(sem informação)') AS {agrupar_por}, erp, COUNT(*) AS documentos, "
            f"ROUND(SUM(valor), 2) AS valor_total, ROUND(AVG(valor), 2) AS ticket_medio "
            f"FROM {self._docs(inicio, fim, erp)} GROUP BY 1, erp ORDER BY erp, valor_total DESC", args)

    def conciliar(self, inicio: str, fim: str, tolerancia: float = 0.01) -> dict:
        """Cruza os dois ERPs documento a documento."""
        a, b = ERPS
        docs = {erp: {r["documento"]: r for r in self._q(f"SELECT * FROM {self._docs(inicio, fim, erp)}",
                                                         (inicio, fim, erp))} for erp in ERPS}
        so_a = sorted(set(docs[a]) - set(docs[b]))
        so_b = sorted(set(docs[b]) - set(docs[a]))
        divergentes = [
            {"documento": d, f"valor_{a}": docs[a][d]["valor"], f"valor_{b}": docs[b][d]["valor"],
             "diferenca": round(docs[a][d]["valor"] - docs[b][d]["valor"], 2)}
            for d in sorted(set(docs[a]) & set(docs[b]))
            if abs(docs[a][d]["valor"] - docs[b][d]["valor"]) > tolerancia
        ]
        por_dia: dict[str, dict] = {}
        for erp in ERPS:
            for r in docs[erp].values():
                dia = por_dia.setdefault(r["data"], {f"docs_{e}": 0 for e in ERPS} | {f"valor_{e}": 0.0 for e in ERPS})
                dia[f"docs_{erp}"] += 1
                dia[f"valor_{erp}"] = round(dia[f"valor_{erp}"] + r["valor"], 2)
        return {
            "periodo": [inicio, fim],
            "totais": {erp: {"documentos": len(docs[erp]),
                             "valor": round(sum(r["valor"] for r in docs[erp].values()), 2)} for erp in ERPS},
            "documentos_em_ambos": len(set(docs[a]) & set(docs[b])),
            f"so_no_{a}": [docs[a][d] for d in so_a[:50]], f"qtd_so_no_{a}": len(so_a),
            f"so_no_{b}": [docs[b][d] for d in so_b[:50]], f"qtd_so_no_{b}": len(so_b),
            "valores_divergentes": divergentes[:50], "qtd_valores_divergentes": len(divergentes),
            "por_dia": [{"data": d, **v} for d, v in sorted(por_dia.items())],
        }

    def importacoes(self) -> list[dict]:
        return self._q("SELECT erp, arquivo, linhas, inicio, fim, em FROM importacoes ORDER BY em DESC LIMIT 30")

    # ----------------------------------------------------------------- faturas
    def registrar_fatura(self, f: dict) -> dict:
        with self.db:
            cur = self.db.execute(
                "INSERT OR REPLACE INTO faturas (email_uid, tipo, emitente, nif_emitente, numero, data_emissao, "
                "vencimento, valor, moeda, referencia, resumo, registrado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (f["email_uid"], f["tipo"], f["emitente"], f.get("nif_emitente"), f["numero"],
                 f.get("data_emissao"), f.get("vencimento"), f.get("valor"), f.get("moeda"), f.get("referencia"),
                 f.get("resumo"), datetime.now().isoformat(timespec="minutes")))
        return {"ok": True, "fatura_id": cur.lastrowid, "candidatos_erp": self.candidatos_fatura(cur.lastrowid)}

    def candidatos_fatura(self, fatura_id: int) -> list[dict]:
        """Documentos dos ERPs que podem corresponder à fatura: mesmo número/referência,
        ou mesmo valor com data até 7 dias de diferença."""
        f = self._q("SELECT * FROM faturas WHERE id = ?", (fatura_id,))
        if not f:
            raise ErroDados(f"Fatura {fatura_id} não existe.")
        f = f[0]
        chaves = [normalizar_documento(x) for x in (f["numero"], f["referencia"]) if x]
        achados = []
        if chaves:
            marcas = ",".join("?" * len(chaves))
            achados += [r | {"motivo": "mesmo número"} for r in
                        self._q(f"SELECT erp, documento, data, valor, cliente FROM vendas "
                                f"WHERE documento IN ({marcas}) GROUP BY erp, documento", tuple(chaves))]
        if f["valor"] is not None and f["data_emissao"]:
            d = date.fromisoformat(f["data_emissao"][:10])
            achados += [r | {"motivo": "mesmo valor e data próxima"} for r in self._q(
                f"SELECT erp, documento, data, valor, cliente FROM {self._docs((d - timedelta(7)).isoformat(), (d + timedelta(7)).isoformat())} "
                "WHERE ABS(valor - ?) < 0.01", ((d - timedelta(7)).isoformat(), (d + timedelta(7)).isoformat(), f["valor"]))]
        vistos, unicos = set(), []
        for r in achados:
            if (r["erp"], r["documento"]) not in vistos:
                vistos.add((r["erp"], r["documento"]))
                unicos.append(r)
        return unicos[:10]

    def relacionar_fatura(self, fatura_id: int, erp: str, documento: str) -> dict:
        doc = normalizar_documento(documento)
        if not self._q("SELECT 1 FROM vendas WHERE erp = ? AND documento = ?", (erp, doc)):
            raise ErroDados(f"O documento {documento} não está no {erp}.")
        with self.db:
            n = self.db.execute("UPDATE faturas SET documento_erp = ?, erp = ? WHERE id = ?",
                                (doc, erp, fatura_id)).rowcount
        if not n:
            raise ErroDados(f"Fatura {fatura_id} não existe.")
        return {"ok": True}

    def listar_faturas(self, so_sem_relacao: bool) -> list[dict]:
        filtro = "WHERE documento_erp IS NULL" if so_sem_relacao else ""
        return self._q(f"SELECT * FROM faturas {filtro} ORDER BY data_emissao DESC LIMIT 50")

    # ------------------------------------------------------------------- posts
    def salvar_post(self, rede: str, texto: str, sugestao_imagem: str | None) -> dict:
        with self.db:
            cur = self.db.execute("INSERT INTO posts (rede, texto, sugestao_imagem, status, criado_em) "
                                  "VALUES (?,?,?,'rascunho',?)",
                                  (rede, texto, sugestao_imagem, datetime.now().isoformat(timespec="minutes")))
        return {"ok": True, "post_id": cur.lastrowid, "status": "rascunho"}

    def listar_posts(self) -> list[dict]:
        return self._q("SELECT * FROM posts ORDER BY id DESC LIMIT 20")
