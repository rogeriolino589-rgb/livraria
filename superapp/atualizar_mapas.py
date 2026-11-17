"""Acrescenta ao superapp já publicado os mapas do dia recebidos por e-mail (Diário de Vendas + Mapa de Caixa).

Uso: python superapp/atualizar_mapas.py INDEX_HTML DIA(AAAA-MM-DD) DIARIO.txt CAIXA.txt
Altera só o bloco <script id="etiPend"> do index.html (o superapp grava-os sozinho ao abrir, se baterem certo).
Confere antes com livraria_agentes.interno.mapas_eticadata e não escreve nada se não baterem."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from livraria_agentes.interno.mapas_eticadata import conferir, ler_diario_vendas, ler_mapa_caixa  # noqa: E402


def main(index, dia, diario, caixa):
    html = Path(index).read_text(encoding="utf-8")
    d, c = Path(diario).read_text(encoding="utf-8"), Path(caixa).read_text(encoding="utf-8")
    dif = conferir(ler_diario_vendas(d), ler_mapa_caixa(c))
    if dif:
        print("NÃO BATEM:", dif)
        return 1
    m = re.search(r'<script id="etiPend" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        print("bloco etiPend não encontrado")
        return 1
    pend = [x for x in json.loads(m.group(1).replace("<\\/", "</")) if x["data"] != dia]
    pend.append({"data": dia, "d": d, "c": c})
    pend = sorted(pend, key=lambda x: x["data"])[-62:]  # últimos ~2 meses
    novo = json.dumps(pend, ensure_ascii=False).replace("</", "<\\/")
    html = html[:m.start(1)] + novo + html[m.end(1):]
    Path(index).write_text(html, encoding="utf-8")
    print("ok", dia, len(pend), "mapa(s) no superapp")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:5]))
