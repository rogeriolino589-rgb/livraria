"""Campanha progressiva de contacto: clientes do cadastro e leads do "Caçador de leads".

Cada dia sai o lote seguinte da lista, sem repetir ninguém, até completar todos. Para cada contacto é gerado
um link wa.me com a mensagem já escrita: o vendedor da linha certa toca no link e envia pela linha corporativa
(os números não precisam de estar guardados no telemóvel).

Encaminhamento:
- Moçambique (+258): pela linha do tipo de cliente (igrejas; empresas/instituições/livrarias/revendedores;
  retalho). Leads sem tipo claro são tratados como Cliente VIP (retalho).
- Outros países: linha internacional, mantendo a distinção igreja / instituição / VIP.

    python -m livraria_agentes.campanha importar-leads "CPAD ERP Moçambique — Livraria.html"
    python -m livraria_agentes.campanha lote            # gera (ou mostra) o lote de hoje
    python -m livraria_agentes.campanha progresso

Regras de proteção: limite diário por linha (config/campanha.json), opção de saída em todas as mensagens
("responda SAIR") e quem saiu nunca mais entra na lista. Mensagens em massa para quem não conhece a loja são a
principal causa de bloqueio de números no WhatsApp: comece com poucos contactos por dia.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import html
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import quote

from .loja import Loja
from .pais import PAIS, _achar
from .vendedores import linha_do_tipo

LINHA_INTERNACIONAL = "+258 87 712 7070"

# Indicativos por nome de país (como aparecem nas listas de leads).
INDICATIVOS = {
    "moçambique": "258", "mocambique": "258", "brasil": "55", "argentina": "54", "uruguai": "598", "ghana": "233",
    "gana": "233", "áfrica do sul": "27", "africa do sul": "27", "essuatíni": "268", "essuatini": "268",
    "eswatini": "268", "angola": "244", "zimbábue": "263", "zimbabue": "263", "portugal": "351", "nigéria": "234",
    "nigeria": "234", "estados unidos": "1", "reino unido": "44", "tanzânia": "255", "tanzania": "255",
    "madagascar": "261", "madagáscar": "261", "malawi": "265", "maláui": "265", "zâmbia": "260", "zambia": "260",
    "botsuana": "267", "lesoto": "266", "namíbia": "264", "namibia": "264", "quénia": "254", "quenia": "254",
    "rd congo": "243", "república democrática do congo": "243", "maurícias": "230", "mauricias": "230",
    "ilhas maurício": "230", "cabo verde": "238", "guiné-bissau": "245", "são tomé e príncipe": "239",
    "frança": "33", "canadá": "1", "uganda": "256", "ruanda": "250", "burundi": "257", "camarões": "237",
    "costa do marfim": "225", "senegal": "221", "congo": "242", "etiópia": "251",
}
LUSOFONOS = {"258", "55", "244", "351", "238", "245", "239"}
FRANCOFONOS = {"243", "242", "225", "221", "237", "33", "257", "250", "261", "228", "229", "226", "223", "227"}

PALAVRAS = {
    "Igreja": ["igreja", "church", "eglise", "iglesia", "assembleia", "assembly", "congrega", "templo", "paroquia",
               "parish", "diocese", "ministerio", "ministry", "ministere", "catedral", "cathedral", "capela", "chapel",
               "tabernacle", "tabernaculo", "missao", "mission", "evangel", "pentecost", "baptist", "batista",
               "metodista", "methodist", "presbiter", "luterana", "lutheran", "anglican", "adventist", "nazarene",
               "fjkm", "pastor", "bispo", "bishop", "reverend", "apostol"],
    "Livraria": ["livraria", "papelaria", "bookshop", "bookstore", "librairie", "libreria", "distribuidora"],
    # termos fortes: decidem antes dos de igreja ("Bible College", "Seminário Batista" são instituições)
    "Empresa / instituição": ["escola", "school", "colegio", "college", "universidade", "university", "faculdade",
                              "seminario", "seminary", "instituto", "institute", "empresa", "company", "lda", "ltd",
                              "limitada", "hospital", "governo"],
    # termos genéricos: só contam se nada indicar igreja ("Alliance Church" é igreja)
    "instituição genérica": ["fundacao", "foundation", "associacao", "association", "conselho", "council",
                             "conferencia", "conference", "convencao", "convention", "uniao", "union", "alianca",
                             "alliance", "ong", "organizacao", "organization"],
}


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower()


def classificar(*textos: str) -> str:
    """Igreja, Livraria, Empresa / instituição ou Cliente VIP (quando nada indica outra coisa)."""
    junto = " ".join(_sem_acento(t) for t in textos if t)
    tem = lambda grupo: any(re.search(r"\b" + re.escape(_sem_acento(p)), junto) for p in PALAVRAS[grupo])
    for grupo, tipo in (("Livraria", "Livraria"), ("Empresa / instituição", "Empresa / instituição"),
                        ("Igreja", "Igreja"), ("instituição genérica", "Empresa / instituição")):
        if tem(grupo):
            return tipo
    return "Cliente VIP"


def telefone_internacional(bruto: str, pais: str) -> str | None:
    """Número no formato do WhatsApp (só dígitos, com indicativo) a partir de '+27 12 ...', '(54) 99708-4703'
    ou 'https://wa.me/...'. Em Moçambique só aceita telemóveis."""
    texto = str(bruto or "")
    achado = re.search(r"wa\.me/(\d{8,15})", texto)
    if achado:
        digitos = achado.group(1)
    else:
        digitos = re.sub(r"\D", "", texto)
        if not digitos:
            return None
        if texto.strip().startswith("+") or texto.strip().startswith("00"):
            digitos = digitos[2:] if texto.strip().startswith("00") else digitos
        else:
            indicativo = INDICATIVOS.get(_sem_acento(pais)) or INDICATIVOS.get(str(pais or "").lower())
            if not indicativo:
                return None
            digitos = indicativo + digitos.lstrip("0")
    if digitos.startswith("258"):
        numeros = PAIS.numeros_whatsapp(digitos) if PAIS.indicativo == "258" else [digitos]
        return numeros[0] if numeros else None
    return digitos if 9 <= len(digitos) <= 15 else None


def lingua_do_numero(numero: str) -> str:
    for tamanho in (3, 2, 1):
        prefixo = numero[:tamanho]
        if prefixo in LUSOFONOS:
            return "pt"
        if prefixo in FRANCOFONOS:
            return "fr"
    return "en"


MENSAGENS = {
    "pt": {
        "Igreja": ("Paz do Senhor{nome}! Escrevemos da {loja}, filial da CPAD — Casa Publicadora das Assembleias de "
                   "Deus. Servimos igrejas com Bíblias, Lições Bíblicas da Escola Dominical, Harpa Cristã e livros "
                   "cristãos, com condições especiais para compras da igreja. Podemos enviar o catálogo?"),
        "Empresa / instituição": ("Olá{nome}! Escrevemos da {loja} (CPAD — Casa Publicadora das Assembleias de "
                                  "Deus). Fornecemos Bíblias, livros e materiais cristãos para instituições, com "
                                  "condições especiais para compras em quantidade. Podemos enviar o catálogo?"),
        "Livraria": ("Olá{nome}! Escrevemos da {loja} (CPAD). Temos condições especiais de revenda para livrarias: "
                     "Bíblias, Harpa Cristã, Lições Bíblicas e livros cristãos. Podemos enviar o catálogo e as "
                     "condições?"),
        "Cliente VIP": ("Olá{nome}! Aqui é da {loja} (CPAD). Temos Bíblias, livros cristãos, Harpa Cristã e Lições "
                        "Bíblicas para a sua edificação e para oferecer. Quer conhecer as novidades?"),
        "rodape": "\n\n{contactos}\nPara não receber mais mensagens, responda SAIR.",
    },
    "en": {
        "Igreja": ("Blessings{nome}! We are writing from {loja}, part of CPAD — the Assemblies of God Publishing "
                   "House. We serve churches with Bibles, Sunday School lessons, hymnals and Christian books, with "
                   "special terms for church orders. May we send you our catalogue?"),
        "Empresa / instituição": ("Hello{nome}! We are writing from {loja} (CPAD — Assemblies of God Publishing "
                                  "House). We supply Bibles, books and Christian materials to institutions, with "
                                  "special terms for bulk orders. May we send you our catalogue?"),
        "Livraria": ("Hello{nome}! This is {loja} (CPAD). We offer special reseller terms for bookshops: Bibles, "
                     "hymnals, Sunday School lessons and Christian books. May we send you the catalogue and terms?"),
        "Cliente VIP": ("Hello{nome}! This is {loja} (CPAD). We have Bibles, Christian books and Sunday School "
                        "materials. Would you like to see what's new?"),
        "rodape": "\n\n{contactos}\nTo stop receiving messages, reply STOP.",
    },
    "fr": {
        "Igreja": ("Que la paix du Seigneur soit avec vous{nome} ! Nous vous écrivons de {loja}, filiale de la CPAD "
                   "— maison d'édition des Assemblées de Dieu. Nous servons les églises avec des Bibles, des leçons "
                   "d'École du dimanche, des recueils de cantiques et des livres chrétiens, à des conditions "
                   "spéciales. Pouvons-nous vous envoyer notre catalogue ?"),
        "Empresa / instituição": ("Bonjour{nome} ! Nous vous écrivons de {loja} (CPAD). Nous fournissons des "
                                  "Bibles, des livres et du matériel chrétien aux institutions, à des conditions "
                                  "spéciales pour les achats en quantité. Pouvons-nous vous envoyer le catalogue ?"),
        "Livraria": ("Bonjour{nome} ! Ici {loja} (CPAD). Nous proposons des conditions de revente aux librairies : "
                     "Bibles, cantiques, leçons d'École du dimanche et livres chrétiens. Pouvons-nous vous envoyer le "
                     "catalogue ?"),
        "Cliente VIP": ("Bonjour{nome} ! Ici {loja} (CPAD). Nous avons des Bibles, des livres chrétiens et du "
                        "matériel d'École du dimanche. Voulez-vous découvrir les nouveautés ?"),
        "rodape": "\n\n{contactos}\nPour ne plus recevoir de messages, répondez STOP.",
    },
}

CONFIG_PADRAO = {"por_linha_por_dia": 40, "paises_excluidos": [], "incluir_cadastro": True, "incluir_leads": True}


def configuracao() -> dict:
    arq = _achar("config/campanha.json")
    extra = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    return {**CONFIG_PADRAO, **{k: v for k, v in extra.items() if not k.startswith("_")}}


# ------------------------------------------------------------------ leads
FUNCAO_ALVO = re.compile(r"funcao-alvo|nao representa pessoa|a identificar|a enriquecer")  # regra do ERP
MAX_REGISTOS_POR_NUMERO = 3  # acima disto é número de central/diretório ("número partilhado" no ERP)


def _numero_whatsapp_comprovado(lead: dict) -> str | None:
    """Só aceita números com WhatsApp comprovado na fonte: campo WhatsApp, link wa.me, lista de contactos de
    WhatsApp da CPAD ou nota "WhatsApp publicado". Telefones sem essa prova são ignorados."""
    pais = lead.get("pa")
    for campo in ("wa", "lk"):
        numero = telefone_internacional(lead.get(campo), pais)
        if numero:
            return numero
    prova = _sem_acento(f"{lead.get('tipo') or ''} {lead.get('obs') or ''}")
    if "whatsapp" in prova:
        for campo in ("t1", "t2"):
            numero = telefone_internacional(lead.get(campo), pais)
            if numero:
                return numero
    return None


def parece_nome(rotulo: str) -> bool:
    """O rótulo guardado no telemóvel identifica o contacto? Siglas de grupos de WhatsApp ("SBT", "95 Faof"),
    países e nomes contam (são contactos verdadeiros, guardados pela equipa); só não serve rótulo vazio ou feito
    apenas de emojis e símbolos."""
    return bool(re.search(r"\w", str(rotulo or ""), flags=re.UNICODE))


def _nome_do_rotulo(lead: dict) -> str:
    """Contactos da lista de WhatsApp da CPAD guardam o nome (ou a sigla do grupo de WhatsApp de onde vieram) no
    rótulo, na nota de origem."""
    achado = re.search(r"Rótulo salvo no WhatsApp[^:]*:\s*(.+)$", str(lead.get("obs") or ""))
    rotulo = achado.group(1).strip() if achado else ""
    return rotulo if parece_nome(rotulo) else ""


def limpar_leads(brutos: list[dict]) -> tuple[list[dict], dict]:
    """Tira funções-alvo, contactos sem WhatsApp comprovado, sem nome, números de central (partilhados por mais
    de 3 registos) e repetidos. Devolve os leads limpos (um por número) e a contagem do que saiu."""
    saiu = {"funcao_alvo": 0, "sem_whatsapp_comprovado": 0, "sem_nome": 0, "numero_partilhado": 0, "repetidos": 0}
    candidatos = []
    for lead in brutos:
        texto = _sem_acento(f"{lead.get('tipo') or ''} {lead.get('obs') or ''} {lead.get('org') or ''}")[:400]
        if lead.get("tipo") == "A enriquecer" or FUNCAO_ALVO.search(texto):
            saiu["funcao_alvo"] += 1
            continue
        numero = _numero_whatsapp_comprovado(lead)
        if not numero:
            saiu["sem_whatsapp_comprovado"] += 1
            continue
        nome = lead.get("nome") or lead.get("org") or _nome_do_rotulo(lead)
        if not str(nome or "").strip():
            saiu["sem_nome"] += 1
            continue
        candidatos.append({**lead, "numero": numero, "nome": nome})
    contagem = {}
    for c in candidatos:
        contagem[c["numero"]] = contagem.get(c["numero"], 0) + 1
    limpos, vistos = [], set()
    for c in sorted(candidatos, key=lambda c: (not c.get("nome"), c["id"])):
        if contagem[c["numero"]] > MAX_REGISTOS_POR_NUMERO:
            saiu["numero_partilhado"] += 1
            continue
        if c["numero"] in vistos:
            saiu["repetidos"] += 1
            continue
        vistos.add(c["numero"])
        limpos.append(c)
    return limpos, saiu


def importar_leads(caminho: Path, destino: Path) -> dict:
    """Lê as listas do Caçador de leads guardadas na página do ERP (blocos seed, seed2...seed7), limpa-as
    e guarda só os contactos com WhatsApp comprovado, um por número."""
    texto = Path(caminho).read_text(encoding="utf-8", errors="replace")
    brutos = []
    for bloco, dados in re.findall(r'<script id="(seed\d?)" type="text/plain">([^<]+)</script>', texto):
        if bloco in ("seed8", "seed9"):
            continue  # produtos e clientes
        conteudo = json.loads(gzip.decompress(base64.b64decode(dados)).decode("utf-8"))
        lista = conteudo.get("L", []) if isinstance(conteudo, dict) else conteudo
        for i, lead in enumerate(lista):
            brutos.append({**{k: lead.get(k) for k in ("pa", "org", "nome", "cargo", "tipo", "den", "ent", "t1",
                                                       "t2", "wa", "lk", "pr", "ci", "obs")}, "id": f"{bloco}-{i}"})
    limpos, saiu = limpar_leads(brutos)
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    Path(destino).write_text(json.dumps([{k: v for k, v in l.items() if k != "obs"} for l in limpos],
                                        ensure_ascii=False), encoding="utf-8")
    return {"lidos": len(brutos), "guardados": len(limpos), "eliminados": saiu}


NOME_GENERICO = re.compile(r"\b(clientes? diversos|cl+i+ente sem nome|sem nome|consumidor final|balcao|anonimo)\b")


def contactos(loja: Loja, leads: list[dict], config: dict | None = None) -> list[dict]:
    """Lista ordenada e sem repetidos: cadastro primeiro, depois leads de prioridade ALTA, MÉDIA e o resto."""
    config = config or configuracao()
    excluidos = {_sem_acento(p) for p in config["paises_excluidos"]}
    saida, vistos = [], set(loja.dados.get("optout", {}))

    def junta(contacto: dict) -> None:
        if contacto["numero"] in vistos:
            return
        vistos.add(contacto["numero"])
        mz = contacto["numero"].startswith("258")
        contacto["linha"] = (linha_do_tipo(contacto["tipo"]) if mz else None) or LINHA_INTERNACIONAL
        contacto["lingua"] = lingua_do_numero(contacto["numero"])
        saida.append(contacto)

    if config["incluir_cadastro"]:
        cadastro = [c for c in loja.dados.get("cadastro_clientes", []) if not NOME_GENERICO.search(_sem_acento(c["nome"]))]
        usos: dict[str, int] = {}
        for c in cadastro:
            for numero in c.get("whatsapp", [])[:1]:
                usos[numero] = usos.get(numero, 0) + 1
        for c in cadastro:
            for numero in c.get("whatsapp", [])[:1]:
                if usos[numero] > MAX_REGISTOS_POR_NUMERO:
                    continue  # número de central, usado por vários clientes
                tipo = c["tipo"] if c["tipo"] not in ("Cliente", "Pastor", "Missionário") else "Cliente VIP"
                tipo = "Livraria" if tipo in ("Revendedor", "Pastor revendedor") else tipo
                junta({"id": f"cliente-{c['id_erp']}", "origem": "cadastro", "nome": c["nome"], "tipo": tipo,
                       "tipo_cadastro": c["tipo"], "numero": numero, "pais": "Moçambique"})
    if config["incluir_leads"]:
        ordem = {"ALTA": 0, "MÉDIA": 1, "MEDIA": 1}
        for lead in sorted(leads, key=lambda l: ordem.get(str(l.get("pr") or "").upper(), 2)):
            if _sem_acento(lead.get("pa")) in excluidos:
                continue
            numero = lead.get("numero") or _numero_whatsapp_comprovado(lead)
            if not numero:
                continue
            tipo = classificar(lead.get("org"), lead.get("cargo"), lead.get("tipo"), lead.get("den"),
                               lead.get("ent"))
            junta({"id": lead["id"], "origem": "lead", "nome": lead.get("nome") or lead.get("org") or "",
                   "organizacao": lead.get("org") or "", "tipo": tipo, "numero": numero,
                   "pais": lead.get("pa") or ""})
    return saida


def mensagem(contacto: dict) -> str:
    textos = MENSAGENS[contacto["lingua"]]
    nome = contacto.get("nome") or ""
    trata = f", {nome.split()[0]}" if contacto["origem"] == "cadastro" and nome and contacto["tipo"] == "Cliente VIP" else ""
    corpo = textos[contacto["tipo"]].format(nome=trata, loja=PAIS.nome_loja)
    contactos_loja = f"WhatsApp {contacto['linha']}" + (f" · {PAIS.email}" if PAIS.email else "")
    return corpo + textos["rodape"].format(contactos=contactos_loja)


def link(contacto: dict) -> str:
    return f"https://wa.me/{contacto['numero']}?text={quote(mensagem(contacto))}"


# ------------------------------------------------------------------ lotes
class Campanha:
    def __init__(self, loja: Loja, pasta: Path):
        self.loja, self.pasta = loja, Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.arq_estado = self.pasta / "campanha.json"
        self.arq_leads = self.pasta / "leads.json"

    def _estado(self) -> dict:
        if self.arq_estado.exists():
            return json.loads(self.arq_estado.read_text(encoding="utf-8"))
        return {"feitos": {}, "lotes": {}}

    def _salvar(self, estado: dict) -> None:
        self.arq_estado.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")

    def lista(self) -> list[dict]:
        leads = json.loads(self.arq_leads.read_text(encoding="utf-8")) if self.arq_leads.exists() else []
        sem_whatsapp = self._estado().get("sem_whatsapp", {})
        return [c for c in contactos(self.loja, leads) if c["id"] not in sem_whatsapp]

    def marcar_sem_whatsapp(self, contacto_id: str) -> dict:
        """O vendedor abriu o link e o WhatsApp disse que o número não está registado: sai da lista."""
        estado = self._estado()
        estado.setdefault("sem_whatsapp", {})[contacto_id] = self.loja.relogio().isoformat(timespec="minutes")
        self._salvar(estado)
        return {"ok": True, "id": contacto_id}

    def lote(self, dia: date | None = None) -> dict:
        """Lote do dia: o seguinte da lista em cada linha (o mesmo se já foi gerado hoje)."""
        dia = (dia or self.loja.relogio().date()).isoformat()
        estado = self._estado()
        if dia in estado["lotes"]:
            return estado["lotes"][dia]
        limite = configuracao()["por_linha_por_dia"]
        optout = set(self.loja.dados.get("optout", {}))
        por_linha: dict[str, list] = {}
        for c in self.lista():
            if c["id"] in estado["feitos"] or c["numero"] in optout:
                continue
            fila = por_linha.setdefault(c["linha"], [])
            if len(fila) < limite:
                fila.append({**c, "link": link(c)})
        for fila in por_linha.values():
            for c in fila:
                estado["feitos"][c["id"]] = dia
        lote = {"dia": dia, "linhas": por_linha}
        estado["lotes"][dia] = lote
        self._salvar(estado)
        return lote

    def progresso(self) -> dict:
        estado, lista = self._estado(), self.lista()
        limite = configuracao()["por_linha_por_dia"]
        por_linha: dict[str, dict] = {}
        for c in lista:
            p = por_linha.setdefault(c["linha"], {"total": 0, "contactados": 0})
            p["total"] += 1
            p["contactados"] += c["id"] in estado["feitos"]
        for p in por_linha.values():
            falta = p["total"] - p["contactados"]
            p["faltam"] = falta
            p["dias_para_terminar"] = -(-falta // limite) if limite else None
        return {"por_linha_por_dia": limite, "linhas": por_linha,
                "sairam_da_lista": len(self.loja.dados.get("optout", {})),
                "sem_whatsapp": len(estado.get("sem_whatsapp", {}))}

    def pagina(self, lote: dict, linha: str | None = None, chave: str | None = None) -> str:
        """Página com os links do dia, para o vendedor tocar e enviar."""
        blocos = []
        for numero_linha, fila in lote["linhas"].items():
            if linha and re.sub(r"\D", "", linha) != re.sub(r"\D", "", numero_linha):
                continue
            itens = "".join(
                f'<li><b>{html.escape(c["nome"] or c.get("organizacao") or "Contacto")}</b> '
                f'<small>{html.escape(c["tipo"])} · {html.escape(c["pais"])} · +{c["numero"]}</small><br>'
                f'<a class="b" href="{html.escape(c["link"])}" target="_blank">Abrir no WhatsApp e enviar</a>'
                + (f' <a class="n" href="/campanha/marcar?chave={quote(chave)}&id={quote(c["id"])}" target="_blank">'
                   '❌ Não tem WhatsApp</a>' if chave else "") + '</li>'
                for c in fila)
            blocos.append(f"<h2>Linha {html.escape(numero_linha)} — {len(fila)} contacto(s)</h2><ol>{itens}</ol>")
        return ("<!doctype html><html lang='pt'><head><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                f"<title>Contactos de {lote['dia']}</title><style>body{{font:16px system-ui;margin:16px;"
                "max-width:720px}}li{margin:12px 0}a.b{display:inline-block;margin-top:4px;padding:8px 12px;"
                "background:#25d366;color:#04210f;border-radius:8px;text-decoration:none;font-weight:600}"
                "small{color:#555}a.n{margin-left:8px;color:#b00020;font-size:14px}</style></head><body>"
                f"<h1>Contactos do dia {lote['dia']}</h1><p>Envie pela linha indicada (a linha corporativa do seu "
                "setor). Toque no botão, confira a mensagem e envie. Quem responder SAIR sai da lista.</p>"
                + ("".join(blocos) or "<p>Nada para enviar hoje.</p>") + "</body></html>")


def main() -> None:
    from .config import PASTA_ESTADO, abrir

    parser = argparse.ArgumentParser(description="Campanha progressiva de contacto")
    sub = parser.add_subparsers(dest="comando", required=True)
    imp = sub.add_parser("importar-leads")
    imp.add_argument("caminho")
    lt = sub.add_parser("lote")
    lt.add_argument("--html", help="Grava a página com os links neste ficheiro")
    sub.add_parser("progresso")
    args = parser.parse_args()
    loja, _ = abrir()
    campanha = Campanha(loja, PASTA_ESTADO / "campanha")
    if args.comando == "importar-leads":
        print(json.dumps(importar_leads(Path(args.caminho), campanha.arq_leads), ensure_ascii=False))
    elif args.comando == "lote":
        lote = campanha.lote()
        if args.html:
            Path(args.html).write_text(campanha.pagina(lote), encoding="utf-8")
        print(json.dumps({linha: len(f) for linha, f in lote["linhas"].items()}, ensure_ascii=False))
    else:
        print(json.dumps(campanha.progresso(), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
