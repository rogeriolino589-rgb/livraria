"""Importa o catálogo de produtos da CPAD para o robô.

    python -m livraria_agentes.importar_catalogo CAMINHO

CAMINHO pode ser:
- a página HTML do "CPAD ERP Moçambique — Livraria" (os produtos ficam no bloco `seed8` da página);
- um JSON com a lista [código, ISBN, título, categoria, preço, stock];
- uma planilha .xlsx ou .csv com as colunas código, ISBN, título, categoria, preço e stock.

O catálogo é o mesmo em todos os países: em cada loja, a importação acrescenta os produtos novos e
atualiza os existentes, mantendo o stock local e os preços ajustados à mão. Fora de Moçambique, os preços
são convertidos para a moeda local (conversao_precos no perfil do país) ou vêm de uma tabela local (--precos).
Pedidos, clientes, tarefas e o resto ficam como estão.
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

from .loja import PREFIXOS_CPAD, ErroLoja, Loja
from .pais import PAIS

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
                       "preco": round(float(preco or 0), 2), "estoque": max(int(stock or 0), 0), "sinopse": "",
                       "marca": "CPAD" if str(categoria).strip().upper().startswith("CPAD")
                       or str(isbn or "").startswith(PREFIXOS_CPAD) else ""})
    return livros


def _converter_preco(preco_origem: float, fator: float | None, arredondar: float) -> float:
    if not preco_origem:
        return 0.0
    if fator is None:
        return round(preco_origem, 2)
    valor = preco_origem * fator
    return round(round(valor / arredondar) * arredondar, 2) if arredondar else round(valor, 2)


def _ler_precos_locais(caminho: Path | None) -> dict[str, float]:
    """Tabela de preços do país (planilha/CSV com código e preço): substitui a conversão automática."""
    if not caminho:
        return {}
    from .interno.base import _chave, _linhas_arquivo, ler_valor

    linhas = _linhas_arquivo(Path(caminho))
    for i, linha in enumerate(linhas[:30]):
        cab = [_chave(c) for c in linha]
        col_cod = next((cab.index(o) for o in ("codigo", "cod", "referencia", "ref", "artigo") if o in cab), None)
        col_preco = next((cab.index(o) for o in ("preco", "pv", "pvp", "precovenda", "precodevenda", "valor")
                          if o in cab), None)
        if col_cod is not None and col_preco is not None:
            break
    else:
        raise ErroLoja("Na tabela de preços, não reconheci as colunas código e preço.")
    tabela = {}
    for linha in linhas[i + 1:]:
        if max(col_cod, col_preco) < len(linha) and linha[col_cod]:
            preco = ler_valor(linha[col_preco])
            if preco:
                tabela[str(linha[col_cod]).strip()] = round(preco, 2)
    return tabela


def importar(loja: Loja, caminho: Path, precos_locais: Path | None = None, fator: float | None = None,
             stock_da_fonte: bool | None = None) -> dict:
    """Atualiza o catálogo da loja com o catálogo comum da CPAD.

    - Produtos novos entram; os que já existem têm título, ISBN e categoria atualizados.
    - Preço: tabela local (se houver) > preço ajustado à mão na loja > preço da fonte convertido para a moeda
      do país (conversao_precos no perfil, ou o fator indicado).
    - Stock: cada país tem o seu. Por padrão só a loja da moeda de origem (Moçambique) usa o stock da fonte;
      nos outros países os produtos novos entram com stock 0 e o stock existente não muda.
    """
    conversao = PAIS.conversao_precos or {}
    origem = conversao.get("de", PAIS.moeda)
    if fator is None and PAIS.moeda != origem:
        fator = conversao.get("fator")
    tabela = _ler_precos_locais(precos_locais)
    if PAIS.moeda != origem and fator is None and not tabela:
        raise ErroLoja(f"Os preços do catálogo estão em {origem} e esta loja vende em {PAIS.moeda}: defina "
                       f"conversao_precos.fator em config/paises/{PAIS.codigo}.json, use --fator ou --precos.")
    if stock_da_fonte is None:
        stock_da_fonte = PAIS.moeda == origem
    arredondar = float(conversao.get("arredondar") or 0)

    fonte = converter(ler(caminho))
    if not fonte:
        raise ErroLoja("Nenhum produto encontrado.")
    novos = atualizados = 0
    with loja._trava:
        # Na primeira importação, o catálogo de exemplo sai; depois, o catálogo real é atualizado.
        atuais = {l["id"]: l for l in loja.dados["livros"]} if "catalogo" in loja.dados else {}
        for produto in fonte:
            preco = tabela.get(produto["id"], _converter_preco(produto["preco"], fator, arredondar))
            existente = atuais.get(produto["id"])
            if existente is None:
                atuais[produto["id"]] = {**produto, "preco": preco,
                                         "estoque": produto["estoque"] if stock_da_fonte else 0}
                novos += 1
                continue
            for campo in ("titulo", "isbn", "genero", "marca"):
                existente[campo] = produto[campo]
            if produto["id"] in tabela or not existente.get("preco_manual"):
                existente["preco"] = preco
            if stock_da_fonte:
                existente["estoque"] = produto["estoque"]
            atualizados += 1
        loja.dados["livros"] = list(atuais.values())
        loja.dados["catalogo"] = {"fonte": Path(caminho).name, "importado_em": datetime.now().isoformat(timespec="minutes"),
                                  "produtos": len(atuais), "moeda": PAIS.moeda, "fator": fator}
        loja.salvar()
    livros = loja.dados["livros"]
    com_preco = [l for l in livros if l["preco"] > 0]
    return {"produtos": len(livros), "novos": novos, "atualizados": atualizados, "com_preco": len(com_preco),
            "com_preco_marca_cpad": sum(1 for l in com_preco if l.get("marca") == "CPAD"),
            "com_preco_e_stock": sum(1 for l in com_preco if l["estoque"] > 0),
            "por_categoria": {c: sum(1 for l in com_preco if l["genero"] == c)
                              for c in sorted({l["genero"] for l in com_preco})}}


def main() -> None:
    from .config import abrir

    parser = argparse.ArgumentParser(description="Importa / atualiza o catálogo comum de produtos da CPAD")
    parser.add_argument("caminho", help="Página do ERP, JSON ou planilha com o catálogo comum")
    parser.add_argument("--precos", help="Planilha/CSV com os preços locais (código e preço)")
    parser.add_argument("--fator", type=float, help="Converte os preços de origem: preço local = preço × fator")
    parser.add_argument("--stock-da-fonte", action="store_true", help="Usa o stock da fonte também neste país")
    args = parser.parse_args()
    loja, _ = abrir()
    resultado = importar(loja, Path(args.caminho), args.precos, args.fator, True if args.stock_da_fonte else None)
    print(json.dumps(resultado, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
