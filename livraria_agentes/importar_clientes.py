"""Importa a lista de clientes da CPAD (igrejas, pastores, revendedores, clientes VIP...).

    python -m livraria_agentes.importar_clientes CAMINHO

CAMINHO pode ser a página HTML do "CPAD ERP Moçambique — Livraria" (os clientes ficam no bloco `seed9`),
um JSON com a lista [id, nome, tipo, telefone, cidade, bairro, mês de aniversário] ou uma planilha
.xlsx/.csv com essas colunas.

Os números moçambicanos (84 123 4567) viram o formato do WhatsApp (258841234567). Quando um cliente da
lista escreve no WhatsApp, os agentes já sabem o nome e o tipo dele. Nomes que o próprio cliente deu na
conversa não são substituídos. Os dados ficam só na base do robô (dados/estado), fora do Git.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from .loja import ErroLoja, Loja

TIPOS = {"CLIENTE VIP": "Cliente VIP", "PASTOR": "Pastor", "IGREJA": "Igreja", "MISSIONARIOS": "Missionário",
         "EMPRESAS / INSTITUIÇÕES": "Empresa / instituição", "REVENDEDOR": "Revendedor",
         "PASTOR REVENDEDOR": "Pastor revendedor", "LIVRARIA": "Livraria", "": "Cliente"}
MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro",
         "Novembro", "Dezembro"]


def numeros_whatsapp(telefone: str) -> list[str]:
    """'84 727 9956' -> ['258847279956']; '847279956/827838470' -> os dois; outros formatos -> []."""
    digitos = re.sub(r"\D", "", str(telefone or ""))
    if len(digitos) == 12 and digitos.startswith("258"):
        return [digitos]
    if len(digitos) == 9 and digitos[0] == "8":
        return ["258" + digitos]
    if len(digitos) == 18:  # dois números juntos
        return [n for parte in (digitos[:9], digitos[9:]) for n in numeros_whatsapp(parte)]
    partes = [p for p in re.split(r"[/,;]| e ", str(telefone or "")) if p.strip()]
    if len(partes) > 1:
        return [n for p in partes for n in numeros_whatsapp(p)]
    return []


def _linhas_html(caminho: Path) -> list[list]:
    texto = caminho.read_text(encoding="utf-8", errors="replace")
    achado = re.search(r'<script id="seed9" type="text/plain">([^<]+)</script>', texto)
    if not achado:
        raise ErroLoja("Não encontrei a lista de clientes (bloco seed9) nesta página.")
    return json.loads(gzip.decompress(base64.b64decode(achado.group(1))).decode("utf-8"))


def _linhas_planilha(caminho: Path) -> list[list]:
    from .interno.base import _chave, _linhas_arquivo

    linhas = _linhas_arquivo(caminho)
    nomes = {"id": ["id", "codigo", "cod", "numero"], "nome": ["nome", "cliente", "designacao"],
             "tipo": ["tipo", "categoria", "classe"], "tel": ["telefone", "telemovel", "contacto", "celular", "tel"],
             "cidade": ["cidade", "localidade", "provincia"], "bairro": ["bairro", "endereco", "morada"],
             "mes": ["mes", "mesaniversario", "aniversario"]}
    for i, linha in enumerate(linhas[:30]):
        cab = [_chave(c) for c in linha]
        mapa = {campo: next((cab.index(o) for o in opcoes if o in cab), None) for campo, opcoes in nomes.items()}
        if mapa["nome"] is not None:
            break
    else:
        raise ErroLoja("Não reconheci a coluna nome na planilha.")
    pega = lambda linha, campo: (linha[mapa[campo]] if mapa[campo] is not None and mapa[campo] < len(linha)
                                 else None) or ""
    return [[pega(l, "id") or n, pega(l, "nome"), pega(l, "tipo"), pega(l, "tel"), pega(l, "cidade"),
             pega(l, "bairro"), pega(l, "mes")] for n, l in enumerate(linhas[i + 1:], 1) if pega(l, "nome")]


def ler(caminho: Path) -> list[list]:
    caminho = Path(caminho)
    sufixo = caminho.suffix.lower()
    if sufixo in (".html", ".htm"):
        return _linhas_html(caminho)
    if sufixo == ".json":
        return json.loads(caminho.read_text(encoding="utf-8"))
    return _linhas_planilha(caminho)


def importar(loja: Loja, caminho: Path) -> dict:
    cadastro, sem_whatsapp = [], 0
    for id_, nome, tipo, tel, cidade, bairro, mes in (l[:7] for l in ler(caminho)):
        nome = " ".join(str(nome).split())
        if not nome:
            continue
        cidade = str(cidade or "").strip().title()
        registro = {"id_erp": str(id_), "nome": nome, "tipo": TIPOS.get(str(tipo).strip().upper(), str(tipo).title()),
                    "telefone": str(tel or "").strip(), "whatsapp": numeros_whatsapp(tel), "cidade": cidade,
                    "bairro": str(bairro or "").strip(), "mes_aniversario": mes if mes in MESES else ""}
        sem_whatsapp += not registro["whatsapp"]
        cadastro.append(registro)
    if not cadastro:
        raise ErroLoja("Nenhum cliente encontrado.")
    ligados = 0
    with loja._trava:
        loja.dados["cadastro_clientes"] = cadastro
        for registro in cadastro:
            for numero in registro["whatsapp"]:
                atual = loja.dados["clientes"].setdefault(numero, {})
                atual.setdefault("nome", registro["nome"])  # não apaga o nome dado na conversa
                atual.update({"tipo": registro["tipo"], "id_erp": registro["id_erp"], "cidade": registro["cidade"]})
                ligados += 1
        loja.dados["cadastro_info"] = {"fonte": Path(caminho).name,
                                       "importado_em": datetime.now().isoformat(timespec="minutes")}
        loja.salvar()
    return {"clientes": len(cadastro), "numeros_whatsapp": ligados, "sem_numero_valido": sem_whatsapp,
            "por_tipo": dict(Counter(r["tipo"] for r in cadastro).most_common()),
            "cidades_principais": dict(Counter(r["cidade"] or "(sem cidade)" for r in cadastro).most_common(8)),
            "com_mes_de_aniversario": sum(1 for r in cadastro if r["mes_aniversario"])}


def main() -> None:
    from .config import abrir

    parser = argparse.ArgumentParser(description="Importa a lista de clientes")
    parser.add_argument("caminho")
    args = parser.parse_args()
    loja, _ = abrir()
    print(json.dumps(importar(loja, Path(args.caminho)), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
