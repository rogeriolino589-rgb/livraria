"""Importa o catálogo de produtos da CPAD para o robô.

    python -m livraria_agentes.importar_catalogo CAMINHO

CAMINHO pode ser:
- a página HTML do "CPAD ERP Moçambique — Livraria" (os produtos ficam no bloco `seed8` da página);
- um JSON com a lista [código, ISBN, título, categoria, preço, stock];
- uma planilha .xlsx ou .csv com as colunas código, ISBN, título, categoria, preço e stock.

Substitui só o catálogo: pedidos, clientes, tarefas e o resto ficam como estão.
Atenção: alterações feitas dentro da página do ERP (preços ou stock editados no navegador) ficam guardadas
só nesse navegador e não vêm no arquivo da página. Para dados atualizados, exporte uma planilha do ERP.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import re
from datetime import datetime
from pathlib import Path

from .loja import ErroLoja, Loja

CATEGORIAS = {
    "BIBILIAS": "Bíblias", "BIBLIAS": "Bíblias", "CPAD - BIBLIAS": "Bíblias",
    "LIVROS": "Livros", "CPAD - LIVROS": "Livros", "LIVRO INFANTIL": "Livros infantis",
    "CPAD - LICOES BIBLICAS": "Lições Bíblicas (Escola Dominical)",
    "HARPA CRISTA": "Harpa Cristã", "BRINDES": "Brindes", "CONSIGNADO": "Consignado",
    "CD'S": "CDs", "CPAD - CDS": "CDs", "DVD": "DVDs", "CPAD - DVDS": "DVDs", "": "Sem categoria",
}


def _linhas_html(caminho: Path) -> list[list]:
    texto = caminho.read_text(encoding="utf-8", errors="replace")
    achado = re.search(r'<script id="seed8" type="text/plain">([^<]+)</script>', texto)
    if not achado:
        raise ErroLoja("Não encontrei a lista de produtos (bloco seed8) nesta página.")
    return json.loads(gzip.decompress(base64.b64decode(achado.group(1))).decode("utf-8"))


def _linhas_planilha(caminho: Path) -> list[list]:
    from .interno.base import _linhas_arquivo, _chave, ler_valor

    linhas = _linhas_arquivo(caminho)
    nomes = {"codigo": ["codigo", "cod", "referencia", "ref", "artigo"], "isbn": ["isbn", "codigodebarras", "ean"],
             "titulo": ["titulo", "descricao", "nome", "produto", "designacao"],
             "categoria": ["categoria", "familia", "grupo", "tipo"],
             "preco": ["preco", "pv", "precovenda", "precodevenda", "pvp", "valor"],
             "stock": ["stock", "estoque", "quantidade", "qtd", "existencia", "existencias"]}
    for i, linha in enumerate(linhas[:30]):
        cab = [_chave(c) for c in linha]
        mapa = {campo: next((cab.index(o) for o in opcoes if o in cab), None) for campo, opcoes in nomes.items()}
        if mapa["codigo"] is not None and mapa["titulo"] is not None:
            break
    else:
        raise ErroLoja("Não reconheci as colunas código e título na planilha.")
    saida = []
    for linha in linhas[i + 1:]:
        pega = lambda campo: linha[mapa[campo]] if mapa[campo] is not None and mapa[campo] < len(linha) else None
        if not pega("codigo") or not pega("titulo"):
            continue
        saida.append([str(pega("codigo")).strip(), str(pega("isbn") or "").strip(), str(pega("titulo")).strip(),
                      str(pega("categoria") or "").strip(), ler_valor(pega("preco")) or 0.0,
                      int(ler_valor(pega("stock")) or 0)])
    return saida


def ler(caminho: Path) -> list[list]:
    caminho = Path(caminho)
    sufixo = caminho.suffix.lower()
    if sufixo in (".html", ".htm"):
        return _linhas_html(caminho)
    if sufixo == ".json":
        return json.loads(caminho.read_text(encoding="utf-8"))
    return _linhas_planilha(caminho)


def converter(linhas: list[list]) -> list[dict]:
    livros, vistos = [], set()
    for codigo, isbn, titulo, categoria, preco, stock in (l[:6] for l in linhas):
        codigo = str(codigo).strip()
        if not codigo or codigo in vistos:
            continue
        vistos.add(codigo)
        livros.append({"id": codigo, "isbn": str(isbn or "").strip(), "titulo": " ".join(str(titulo).split()),
                       "autor": "", "genero": CATEGORIAS.get(str(categoria).strip().upper(), str(categoria).title()),
                       "preco": round(float(preco or 0), 2), "estoque": max(int(stock or 0), 0), "sinopse": ""})
    return livros


def importar(loja: Loja, caminho: Path) -> dict:
    livros = converter(ler(caminho))
    if not livros:
        raise ErroLoja("Nenhum produto encontrado.")
    with loja._trava:
        loja.dados["livros"] = livros
        loja.dados["catalogo"] = {"fonte": Path(caminho).name, "importado_em": datetime.now().isoformat(timespec="minutes"),
                                  "produtos": len(livros)}
        loja.salvar()
    com_preco = [l for l in livros if l["preco"] > 0]
    return {"produtos": len(livros), "com_preco": len(com_preco),
            "com_preco_e_stock": sum(1 for l in com_preco if l["estoque"] > 0),
            "por_categoria": {c: sum(1 for l in com_preco if l["genero"] == c)
                              for c in sorted({l["genero"] for l in com_preco})}}


def main() -> None:
    from .config import abrir

    parser = argparse.ArgumentParser(description="Importa o catálogo de produtos")
    parser.add_argument("caminho")
    args = parser.parse_args()
    loja, _ = abrir()
    print(json.dumps(importar(loja, Path(args.caminho)), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
