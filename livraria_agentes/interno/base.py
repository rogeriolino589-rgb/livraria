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
# Os dois ERPs são sequenciais: o ERP19 tem a história até julho de 2022 e o ERP22 daí em diante.
# Cada data tem um único sistema "oficial"; dá para mudar em config/erps.json ("periodo": [inicio, fim]).
PERIODOS_PADRAO = {"erp19": ("2016-01-01", "2022-07-31"), "erp22": ("2022-08-01", "9999-12-31")}
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
                "mes": "substr(data, 1, 7)", "ano": "substr(data, 1, 4)", "cliente": "cliente"}

ESQUEMA = """
CREATE TABLE IF NOT EXISTS vendas (
    erp TEXT NOT NULL, documento TEXT NOT NULL, data TEXT NOT NULL, vendedor TEXT, provincia TEXT,
    cliente TEXT, valor REAL NOT NULL, arquivo TEXT, linha INTEGER);
CREATE INDEX IF NOT EXISTS vendas_erp_data ON vendas (erp, data);
CREATE INDEX IF NOT EXISTS vendas_doc ON vendas (documento);
CREATE TABLE IF NOT EXISTS importacoes (
    hash TEXT PRIMARY KEY, erp TEXT, arquivo TEXT, linhas INTEGER, inicio TEXT, fim TEXT, em TEXT);
CREATE TABLE IF NOT EXISTS faturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT, email_uid TEXT, tipo TEXT, emitente TEXT, nuit_emitente TEXT,
    numero TEXT, data_emissao TEXT, vencimento TEXT, valor REAL, moeda TEXT, referencia TEXT,
    resumo TEXT, documento_erp TEXT, erp TEXT, registrado_em TEXT,
    UNIQUE (email_uid, numero));
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, rede TEXT, texto TEXT, sugestao_imagem TEXT, status TEXT,
    criado_em TEXT);
CREATE TABLE IF NOT EXISTS documentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, hash TEXT UNIQUE, email_uid TEXT, remetente TEXT, assunto TEXT,
    data_email TEXT, nome TEXT, tipo TEXT, tamanho_kb REAL, caminho TEXT, copiado_em TEXT);
CREATE TABLE IF NOT EXISTS movimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, tipo TEXT NOT NULL, valor REAL NOT NULL,
    categoria TEXT NOT NULL, descricao TEXT, forma_pagamento TEXT, referencia TEXT, origem TEXT, registrado_por TEXT,
    registrado_em TEXT);
CREATE INDEX IF NOT EXISTS movimentos_data ON movimentos (data);
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
        self.periodos = {}
        for erp in ERPS:
            inicio, fim = self.config.get(erp, {}).get("periodo", PERIODOS_PADRAO[erp])
            self.periodos[erp] = (date.fromisoformat(inicio).isoformat(), date.fromisoformat(fim).isoformat())

    def _filtro_oficial(self) -> str:
        """Condição SQL que mantém cada documento só no período oficial do seu ERP (datas já validadas)."""
        return "(" + " OR ".join(f"(erp = '{erp}' AND data BETWEEN '{a}' AND '{b}')"
                                 for erp, (a, b) in self.periodos.items()) + ")"

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
        a, b = self.periodos[erp]
        fora = [r for r in registros if not a <= r[2] <= b]
        resultado = {"ok": True, "erp": erp, "arquivo": caminho.name, "linhas_importadas": len(registros),
                     "linhas_ignoradas": ignoradas, "substituidas": apagadas, "periodo": [inicio, fim],
                     "colunas_reconhecidas": colunas}
        if fora:
            resultado["aviso_periodo"] = (
                f"{len(fora)} linha(s) com data fora do período do {erp} ({a} a {b}), entre "
                f"{min(r[2] for r in fora)} e {max(r[2] for r in fora)}. Ficam guardadas, mas não entram nos "
                "totais consolidados (podem ser documentos migrados do outro sistema).")
        return resultado

    def importar_diario_vendas(self, texto_diario: str, texto_caixa: str | None = None,
                               nome: str = "DiarioVendas") -> dict:
        """Importa o Diário de Vendas do Eticadata (texto do PDF diário). O ERP é escolhido pela data.

        Com o Mapa de Caixa do mesmo dia, confere os dois antes de gravar: se não baterem, não grava nada.
        Reimportar o mesmo dia substitui os documentos desse dia (a versão mais nova manda)."""
        from .mapas_eticadata import conferir, ler_diario_vendas, ler_mapa_caixa

        diario = ler_diario_vendas(texto_diario)
        if not diario["documentos"]:
            raise ErroDados("Nenhum documento reconhecido no Diário de Vendas.")
        caixa = ler_mapa_caixa(texto_caixa) if texto_caixa else None
        avisos = conferir(diario, caixa) if caixa else []
        if avisos:
            return {"ok": False, "erro": "O Diário de Vendas não bate com o Mapa de Caixa; nada foi gravado.",
                    "diferencas": avisos}
        hash_ = hashlib.sha256(texto_diario.encode()).hexdigest()
        if self._q("SELECT 1 FROM importacoes WHERE hash = ?", (hash_,)):
            return {"ok": True, "aviso": "Este Diário de Vendas já tinha sido importado.", "arquivo": nome}
        datas = sorted({d["data"] for d in diario["documentos"]})
        erp = next((e for e, (a, b) in self.periodos.items() if a <= datas[0] <= b), "erp22")
        registros = [(erp, normalizar_documento(d["documento"]), d["data"], d["vendedor"], diario["seccao"], None,
                      d["total"], nome, n) for n, d in enumerate(diario["documentos"], start=1)]
        with self.db:
            apagadas = self.db.execute("DELETE FROM vendas WHERE erp = ? AND data BETWEEN ? AND ?",
                                       (erp, datas[0], datas[-1])).rowcount
            self.db.executemany("INSERT INTO vendas VALUES (?,?,?,?,?,?,?,?,?)", registros)
            self.db.execute("INSERT INTO importacoes VALUES (?,?,?,?,?,?,?)",
                            (hash_, erp, nome, len(registros), datas[0], datas[-1],
                             datetime.now().isoformat(timespec="minutes")))
        return {"ok": True, "erp": erp, "arquivo": nome, "documentos": len(registros), "total": diario["total"],
                "descontos": diario["descontos"], "por_meio_pagamento": diario["por_meio_pagamento"],
                "por_vendedor": diario["por_vendedor"], "impostos": diario["impostos"], "substituidas": apagadas,
                "conferido_com_caixa": caixa is not None,
                "fundo_caixa": caixa["fundo_caixa"] if caixa else None}

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
    def _docs(self, erp: str | None = None, oficial: bool = True) -> str:
        """Subconsulta com um registro por documento (soma as linhas de itens do mesmo documento).
        Parâmetros: inicio, fim[, erp]."""
        filtro = "AND erp = ?" if erp else ""
        if oficial:
            filtro += f" AND {self._filtro_oficial()}"
        return (f"(SELECT erp, documento, MIN(data) AS data, MAX(vendedor) AS vendedor, "
                f"MAX(provincia) AS provincia, MAX(cliente) AS cliente, ROUND(SUM(valor), 2) AS valor "
                f"FROM vendas WHERE data BETWEEN ? AND ? {filtro} GROUP BY erp, documento)")

    def resumo_vendas(self, inicio: str, fim: str, agrupar_por: str, erp: str | None) -> list[dict]:
        """Sem `erp`: visão consolidada 2016 até hoje, cada data contada só no seu sistema oficial."""
        if agrupar_por not in AGRUPAMENTOS:
            raise ErroDados(f"Agrupe por: {', '.join(AGRUPAMENTOS)}.")
        expr = AGRUPAMENTOS[agrupar_por]
        args = (inicio, fim, erp) if erp else (inicio, fim)
        ordem = "1" if agrupar_por in ("dia", "mes", "ano") else "valor_total DESC"
        return self._q(
            f"SELECT COALESCE({expr}, '(sem informação)') AS {agrupar_por}, "
            f"GROUP_CONCAT(DISTINCT erp) AS sistemas, COUNT(*) AS documentos, "
            f"ROUND(SUM(valor), 2) AS valor_total, ROUND(AVG(valor), 2) AS ticket_medio "
            f"FROM {self._docs(erp)} GROUP BY 1 ORDER BY {ordem} LIMIT 400", args)

    def verificar_historico(self, inicio: str, fim: str) -> dict:
        """Confere se a história ERP19 (até jul/2022) + ERP22 (desde ago/2022) está completa e sem repetições."""
        por_erp = {}
        for erp, (a, b) in self.periodos.items():
            carregado = self._q("SELECT MIN(data) AS primeira, MAX(data) AS ultima FROM vendas WHERE erp = ?", (erp,))[0]
            dentro = self._q(f"SELECT COUNT(*) AS documentos, ROUND(COALESCE(SUM(valor), 0), 2) AS valor "
                             f"FROM {self._docs(erp)}", (inicio, fim, erp))[0]
            fora = self._q(f"SELECT COUNT(*) AS documentos, ROUND(COALESCE(SUM(valor), 0), 2) AS valor, "
                           f"MIN(data) AS de, MAX(data) AS ate FROM {self._docs(erp, oficial=False)} "
                           f"WHERE data NOT BETWEEN ? AND ?", (inicio, fim, erp, a, b))[0]
            por_erp[erp] = {"periodo_oficial": [a, b if b < "9999" else "hoje"], "dados_carregados": carregado,
                            "no_periodo_oficial": dentro, "fora_do_periodo_oficial": fora}

        por_mes = {r["mes"]: r for r in self.resumo_vendas(inicio, fim, "mes", None)}
        hoje = date.today().isoformat()
        meses, mes = [], date.fromisoformat(inicio).replace(day=1)
        limite = min(fim, hoje)
        while mes.isoformat() <= limite:
            meses.append(mes.isoformat()[:7])
            mes = (mes + timedelta(days=32)).replace(day=1)
        sem_dados = [m for m in meses if m not in por_mes]

        repetidos = self._q(
            "SELECT a.documento, a.data AS data_erp19, a.valor AS valor_erp19, b.data AS data_erp22, "
            "b.valor AS valor_erp22 FROM "
            "(SELECT documento, MIN(data) AS data, ROUND(SUM(valor), 2) AS valor FROM vendas WHERE erp = 'erp19' "
            " GROUP BY documento) a JOIN "
            "(SELECT documento, MIN(data) AS data, ROUND(SUM(valor), 2) AS valor FROM vendas WHERE erp = 'erp22' "
            " GROUP BY documento) b USING (documento) "
            "WHERE a.data BETWEEN ? AND ? OR b.data BETWEEN ? AND ? ORDER BY a.data LIMIT 51",
            (inicio, fim, inicio, fim))

        fim19 = date.fromisoformat(self.periodos["erp19"][1])
        transicao = [m for m in por_mes.values()
                     if abs((date.fromisoformat(m["mes"] + "-01") - fim19.replace(day=1)).days) <= 100]
        return {
            "periodo": [inicio, fim],
            "por_erp": por_erp,
            "meses_sem_nenhum_documento": sem_dados,
            "documentos_com_mesmo_numero_nos_dois_erps": repetidos[:50],
            "qtd_documentos_repetidos": len(repetidos) if len(repetidos) <= 50 else "mais de 50",
            "meses_da_transicao_erp19_para_erp22": transicao,
            "por_ano": self.resumo_vendas(inicio, fim, "ano", None),
        }

    def importacoes(self) -> list[dict]:
        return self._q("SELECT erp, arquivo, linhas, inicio, fim, em FROM importacoes ORDER BY em DESC LIMIT 30")

    # ----------------------------------------------------------------- faturas
    def registrar_fatura(self, f: dict) -> dict:
        with self.db:
            cur = self.db.execute(
                "INSERT OR REPLACE INTO faturas (email_uid, tipo, emitente, nuit_emitente, numero, data_emissao, "
                "vencimento, valor, moeda, referencia, resumo, registrado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (f["email_uid"], f["tipo"], f["emitente"], f.get("nuit_emitente"), f["numero"],
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
                f"SELECT erp, documento, data, valor, cliente FROM {self._docs(oficial=False)} "
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

    def listar_faturas(self, so_sem_relacao: bool, limite: int | None = 50) -> list[dict]:
        filtro = "WHERE documento_erp IS NULL" if so_sem_relacao else ""
        corte = f"LIMIT {int(limite)}" if limite else ""
        return self._q(f"SELECT * FROM faturas {filtro} ORDER BY data_emissao DESC {corte}")

    # ------------------------------------------------------------------- posts
    def salvar_post(self, rede: str, texto: str, sugestao_imagem: str | None) -> dict:
        with self.db:
            cur = self.db.execute("INSERT INTO posts (rede, texto, sugestao_imagem, status, criado_em) "
                                  "VALUES (?,?,?,'rascunho',?)",
                                  (rede, texto, sugestao_imagem, datetime.now().isoformat(timespec="minutes")))
        return {"ok": True, "post_id": cur.lastrowid, "status": "rascunho"}

    def listar_posts(self) -> list[dict]:
        return self._q("SELECT * FROM posts ORDER BY id DESC LIMIT 20")

    # -------------------------------------------------------------- documentos
    def documento_existente(self, hash_: str) -> dict | None:
        r = self._q("SELECT * FROM documentos WHERE hash = ?", (hash_,))
        return r[0] if r else None

    def registrar_documento(self, d: dict) -> int:
        with self.db:
            cur = self.db.execute(
                "INSERT INTO documentos (hash, email_uid, remetente, assunto, data_email, nome, tipo, tamanho_kb, "
                "caminho, copiado_em) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (d["hash"], d["email_uid"], d["remetente"], d["assunto"], d["data_email"], d["nome"], d["tipo"],
                 d["tamanho_kb"], d["caminho"], datetime.now().isoformat(timespec="minutes")))
        return cur.lastrowid

    def listar_documentos(self, busca: str | None, desde: str | None) -> list[dict]:
        sql, args = "SELECT id, nome, tipo, tamanho_kb, remetente, assunto, data_email, caminho FROM documentos WHERE 1=1", []
        if busca:
            sql += " AND (nome LIKE ? OR remetente LIKE ? OR assunto LIKE ?)"
            args += [f"%{busca}%"] * 3
        if desde:
            sql += " AND data_email >= ?"
            args.append(desde)
        return self._q(sql + " ORDER BY data_email DESC LIMIT 100", tuple(args))

    # -------------------------------------------------------------- financeiro
    def registrar_movimento(self, m: dict) -> dict:
        if m["tipo"] not in ("entrada", "saida"):
            raise ErroDados("O tipo é 'entrada' ou 'saida'.")
        if m["valor"] is None or float(m["valor"]) <= 0:
            raise ErroDados("O valor tem de ser positivo.")
        data_ = date.fromisoformat(m["data"]).isoformat()
        with self.db:
            cur = self.db.execute(
                "INSERT INTO movimentos (data, tipo, valor, categoria, descricao, forma_pagamento, referencia, origem, "
                "registrado_por, registrado_em) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (data_, m["tipo"], round(float(m["valor"]), 2), m["categoria"], m.get("descricao"),
                 m.get("forma_pagamento"), m.get("referencia"), m.get("origem", "equipa"), m.get("registrado_por"),
                 datetime.now().isoformat(timespec="minutes")))
        return {"ok": True, "movimento_id": cur.lastrowid}

    def resumo_financeiro(self, inicio: str, fim: str) -> dict:
        totais = {r["tipo"]: r for r in self._q(
            "SELECT tipo, COUNT(*) AS movimentos, ROUND(SUM(valor), 2) AS total FROM movimentos "
            "WHERE data BETWEEN ? AND ? GROUP BY tipo", (inicio, fim))}
        entradas = (totais.get("entrada") or {}).get("total") or 0.0
        saidas = (totais.get("saida") or {}).get("total") or 0.0
        return {
            "periodo": [inicio, fim],
            "entradas": entradas, "saidas": saidas, "saldo": round(entradas - saidas, 2),
            "por_categoria": self._q(
                "SELECT tipo, categoria, COUNT(*) AS movimentos, ROUND(SUM(valor), 2) AS total FROM movimentos "
                "WHERE data BETWEEN ? AND ? GROUP BY tipo, categoria ORDER BY tipo, total DESC", (inicio, fim)),
            "por_forma_pagamento": self._q(
                "SELECT tipo, COALESCE(forma_pagamento, '(não informada)') AS forma, ROUND(SUM(valor), 2) AS total "
                "FROM movimentos WHERE data BETWEEN ? AND ? GROUP BY tipo, forma ORDER BY tipo, total DESC",
                (inicio, fim)),
            "ultimos": self._q("SELECT * FROM movimentos WHERE data BETWEEN ? AND ? ORDER BY data DESC, id DESC "
                               "LIMIT 30", (inicio, fim)),
        }

