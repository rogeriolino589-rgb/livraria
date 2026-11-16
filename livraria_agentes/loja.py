"""Dados e regras de negócio da livraria.

Tudo fica num arquivo JSON simples. Cada operação recebe o telefone do
cliente da conversa: um cliente nunca enxerga pedidos, cobranças ou
agendamentos de outra pessoa, mesmo que peça.
"""

from __future__ import annotations

import json
import re
import os
import secrets
import shutil
import threading
from collections import Counter
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

FUSO = ZoneInfo(os.environ.get("LIVRARIA_FUSO", "Africa/Maputo"))
SEMENTE = Path(__file__).resolve().parent.parent / "dados" / "loja_inicial.json"

# Horário de funcionamento para agendamentos: segunda (0) a sábado (5).
DIAS_ABERTOS = range(0, 6)
HORARIOS = range(9, 18)  # início de cada horário de 1h: 9h às 17h
TIPOS_AGENDAMENTO = {
    "retirada": "Retirada de pedido na loja",
    "consultoria_leitura": "Consultoria de leitura (30 min com um livreiro)",
    "clube_do_livro": "Encontro do clube do livro",
}
VAGAS_POR_HORARIO = 2
PRAZO_PAGAMENTO_DIAS = 2
FRETE_FIXO = 250.0  # meticais

# Política de descontos da CPAD Moçambique para compras de instituições (pode ser ajustada em
# loja.json -> config -> desconto_instituicoes). O mínimo conta só os produtos, sem a taxa de entrega.
POLITICA_DESCONTO = {
    "tipos": ["Igreja", "Empresa / instituição", "Revendedor", "Pastor revendedor", "Livraria"],
    "minimo": 5000.0,
    "taxa_cpad": 0.30,  # só Livros CPAD e Bíblias CPAD
    "generos_cpad_30": ["Livros", "Bíblias"],
    "taxa_outras": 0.15,  # todos os outros produtos (outras marcas e restantes produtos CPAD)
}
# Prefixos de ISBN / código de barras de produtos da CPAD (para os que não estão numa categoria "CPAD -").
PREFIXOS_CPAD = ("9788526", "9798526", "7908234", "7898203")


def meticais(valor: float) -> str:
    """1234.5 -> '1.234,50'."""
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def eh_marca_cpad(livro: dict) -> bool:
    return (livro.get("marca") == "CPAD" or str(livro.get("isbn") or "").startswith(PREFIXOS_CPAD))


def tem_desconto_cpad(livro: dict, regra: dict) -> bool:
    """30% só para Livros CPAD e Bíblias CPAD; Lições, CDs, DVDs e Harpa ficam nos 15%."""
    return eh_marca_cpad(livro) and livro.get("genero") in regra["generos_cpad_30"]


class ErroLoja(Exception):
    """Erro de regra de negócio, com mensagem para o agente repassar."""


PALAVRAS_VAZIAS = {"livro", "livros", "para", "com", "uma", "quero", "tem", "tens", "voces", "sobre", "dos", "das",
                   "que", "por", "preco", "quanto", "custa"}


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return sem_acento.lower()


def agora() -> datetime:
    return datetime.now(FUSO)


def _novo_id(prefixo: str) -> str:
    return f"{prefixo}-{secrets.token_hex(3).upper()}"


class Loja:
    def __init__(self, arquivo: Path, relogio=agora):
        self.arquivo = Path(arquivo)
        self.relogio = relogio
        self._trava = threading.Lock()
        if not self.arquivo.exists():
            self.arquivo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(SEMENTE, self.arquivo)
        self.dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
        for chave in ("tarefas", "pedidos_oracao"):
            self.dados.setdefault(chave, [])
        self.dados.setdefault("contatos", {})

    # ---------------------------------------------------------------- base
    def salvar(self) -> None:
        temp = self.arquivo.with_suffix(".tmp")
        temp.write_text(json.dumps(self.dados, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.arquivo)

    def _livro(self, livro_id: str) -> dict:
        for livro in self.dados["livros"]:
            if livro["id"] == livro_id:
                return livro
        raise ErroLoja(f"Livro {livro_id} não existe no catálogo.")

    def _pedido(self, telefone: str, pedido_id: str) -> dict:
        for pedido in self.dados["pedidos"]:
            if pedido["id"] == pedido_id and pedido["telefone"] == telefone:
                return pedido
        raise ErroLoja(f"Não encontrei o pedido {pedido_id} para este cliente.")

    # ------------------------------------------------------------ clientes
    def nome_cliente(self, telefone: str) -> str | None:
        return self.dados["clientes"].get(telefone, {}).get("nome")

    def ficha_cliente(self, telefone: str) -> dict:
        """O que a loja sabe do cliente desta conversa (nome, tipo, cidade), sem dados de outros clientes."""
        c = self.dados["clientes"].get(telefone, {})
        return {k: c[k] for k in ("nome", "tipo", "cidade") if c.get(k)}

    def buscar_clientes(self, consulta: str, tipo: str | None, cidade: str | None) -> dict:
        """Busca no cadastro de clientes (uso da equipa)."""
        termos = [t for t in re.findall(r"[a-z0-9]+", _normalizar(consulta)) if len(t) > 1]
        tipo_n, cidade_n = _normalizar(tipo or ""), _normalizar(cidade or "")
        achados = []
        for c in self.dados.get("cadastro_clientes", []):
            if tipo_n and tipo_n not in _normalizar(c["tipo"]):
                continue
            if cidade_n and cidade_n not in _normalizar(c["cidade"]):
                continue
            texto = _normalizar(" ".join([c["nome"], c["telefone"], c["cidade"], c["bairro"], c["id_erp"]]))
            if all(t in texto for t in termos):
                achados.append(c)
        return {"encontrados": len(achados), "clientes": achados[:30]}

    def resumo_clientes(self) -> dict:
        cadastro = self.dados.get("cadastro_clientes", [])
        por = lambda campo: dict(Counter(c[campo] or "(sem informação)" for c in cadastro).most_common(15))
        return {"total": len(cadastro), "com_whatsapp": sum(1 for c in cadastro if c["whatsapp"]),
                "por_tipo": por("tipo"), "por_cidade": por("cidade"),
                "contactos_do_whatsapp_desde_sempre": len(self.dados["contatos"])}

    def aniversariantes(self, mes: str) -> dict:
        lista = [c for c in self.dados.get("cadastro_clientes", []) if _normalizar(c["mes_aniversario"]) ==
                 _normalizar(mes)]
        return {"mes": mes, "total": len(lista), "clientes": lista[:100]}

    def registrar_cliente(self, telefone: str, nome: str) -> dict:
        nome = nome.strip()
        if not nome:
            raise ErroLoja("Informe o nome do cliente.")
        with self._trava:
            self.dados["clientes"].setdefault(telefone, {})["nome"] = nome
            self.salvar()
        return {"ok": True, "nome": nome}

    # ------------------------------------------------------------- catálogo
    def buscar_livros(self, consulta: str, genero: str | None, preco_max: float | None,
                      incluir_sem_preco: bool = False) -> list[dict]:
        """Busca sem diferenciar acentos nem maiúsculas ("bíblia" acha "BIBLIA"). Produtos sem preço
        (preço 0 no sistema) não aparecem para clientes."""
        termos = [t for t in re.findall(r"[a-z0-9]+", _normalizar(consulta))
                  if len(t) > 2 and t not in PALAVRAS_VAZIAS]
        genero_n = _normalizar(genero or "")
        achados = []
        for livro in self.dados["livros"]:
            if not incluir_sem_preco and not livro.get("preco"):
                continue
            if genero_n and genero_n not in _normalizar(livro.get("genero", "")):
                continue
            if preco_max is not None and livro["preco"] > preco_max:
                continue
            texto = _normalizar(" ".join(str(livro.get(c) or "") for c in
                                         ("titulo", "autor", "genero", "sinopse", "isbn", "id")))
            pontos = sum(1 for t in termos if t in texto)
            if termos and pontos == 0:
                continue
            achados.append((pontos, livro))
        achados.sort(key=lambda par: (-par[0], par[1].get("estoque", 0) <= 0, par[1]["titulo"]))
        return [
            {k: livro.get(k) for k in ("id", "titulo", "autor", "genero", "marca", "preco", "estoque", "isbn")
             if livro.get(k) not in (None, "")}
            for _, livro in achados[:10]
        ]

    def detalhes_livro(self, livro_id: str) -> dict:
        return dict(self._livro(livro_id))

    # -------------------------------------------------------------- pedidos
    def politica_desconto(self) -> dict:
        return {**POLITICA_DESCONTO, **self.dados.get("config", {}).get("desconto_instituicoes", {})}

    def orcamento(self, telefone: str, itens: list[dict], entrega: str) -> dict:
        """Calcula o pedido com a política de descontos para igrejas, instituições, revendedores e livrarias:
        com compras a partir do mínimo (5.000 MT em produtos), 30% nos Livros e Bíblias CPAD e 15% em todo o resto."""
        if not itens:
            raise ErroLoja("O pedido precisa de pelo menos um produto.")
        if entrega not in ("retirada", "envio"):
            raise ErroLoja("Entrega deve ser 'retirada' ou 'envio'.")
        regra = self.politica_desconto()
        linhas, subtotal = [], 0.0
        for item in itens:
            livro = self._livro(item["livro_id"])
            qtd = int(item["quantidade"])
            if qtd < 1:
                raise ErroLoja("Quantidade deve ser pelo menos 1.")
            if not livro.get("preco"):
                raise ErroLoja(f"'{livro['titulo']}' está sem preço no sistema; chame um atendente.")
            if livro["estoque"] < qtd:
                raise ErroLoja(f"Só há {livro['estoque']} unidade(s) de '{livro['titulo']}' em estoque.")
            valor = round(livro["preco"] * qtd, 2)
            linhas.append({"livro_id": livro["id"], "titulo": livro["titulo"], "quantidade": qtd,
                           "preco_unitario": livro["preco"], "valor": valor,
                           "marca_cpad": eh_marca_cpad(livro), "livro_ou_biblia_cpad": tem_desconto_cpad(livro, regra)})
            subtotal += valor
        subtotal = round(subtotal, 2)
        tipo = self.ficha_cliente(telefone).get("tipo")
        elegivel = tipo in regra["tipos"]
        aplica = elegivel and subtotal >= regra["minimo"]
        desconto_total = 0.0
        for linha in linhas:
            taxa = (regra["taxa_cpad"] if linha["livro_ou_biblia_cpad"] else regra["taxa_outras"]) if aplica else 0.0
            linha["desconto_pct"] = round(taxa * 100)
            linha["desconto"] = round(linha["valor"] * taxa, 2)
            linha["valor_final"] = round(linha["valor"] - linha["desconto"], 2)
            desconto_total += linha["desconto"]
        frete = FRETE_FIXO if entrega == "envio" else 0.0
        if aplica:
            info = f"Desconto de instituição aplicado ({tipo}): 30% em Livros e Bíblias CPAD e 15% nos outros."
        elif elegivel:
            info = (f"{tipo}: faltam {meticais(regra['minimo'] - subtotal)} MT em produtos para ter 30% de desconto "
                    "em Livros e Bíblias CPAD e 15% nos outros.")
        else:
            info = ("Sem desconto: o desconto é para igrejas, instituições, revendedores e livrarias registados no "
                    "cadastro da CPAD; se o cliente disser que é um deles, um atendente confirma.")
        return {"itens": linhas, "subtotal_produtos": subtotal, "desconto": round(desconto_total, 2),
                "entrega": entrega, "frete": frete, "total": round(subtotal - desconto_total + frete, 2),
                "tipo_cliente": tipo, "desconto_aplicado": aplica, "desconto_info": info}

    def criar_pedido(self, telefone: str, itens: list[dict], entrega: str) -> dict:
        if not self.nome_cliente(telefone):
            raise ErroLoja("Registre o nome do cliente (registrar_cliente) antes de criar o pedido.")
        with self._trava:
            conta = self.orcamento(telefone, itens, entrega)
            for linha in conta["itens"]:
                self._livro(linha["livro_id"])["estoque"] -= linha["quantidade"]
            momento = self.relogio()
            pedido = {
                "id": _novo_id("PED"),
                "telefone": telefone,
                "itens": conta["itens"],
                "entrega": entrega,
                "subtotal_produtos": conta["subtotal_produtos"],
                "desconto": conta["desconto"],
                "frete": conta["frete"],
                "total": conta["total"],
                "status": "aguardando_pagamento",
                "criado_em": momento.isoformat(timespec="minutes"),
                "vencimento": (momento.date() + timedelta(days=PRAZO_PAGAMENTO_DIAS)).isoformat(),
                "entregue_em": None,
                "lembretes_cobranca": 0,
                "pos_venda_enviado": False,
            }
            self.dados["pedidos"].append(pedido)
            self._nova_tarefa(f"Separar o pedido {pedido['id']} ({len(conta['itens'])} item(ns), "
                              f"{'entrega ao domicílio' if entrega == 'envio' else 'levantamento na loja'}) "
                              "e aguardar a confirmação do pagamento", None, None, "pedido")
            self.salvar()
        return {**pedido, "desconto_info": conta["desconto_info"], "link_pagamento": self._link(pedido)}

    def consultar_pedidos(self, telefone: str) -> list[dict]:
        return [p for p in self.dados["pedidos"] if p["telefone"] == telefone]

    def cancelar_pedido(self, telefone: str, pedido_id: str) -> dict:
        with self._trava:
            pedido = self._pedido(telefone, pedido_id)
            if pedido["status"] not in ("aguardando_pagamento", "pagamento_em_verificacao"):
                raise ErroLoja(
                    f"O pedido está '{pedido['status']}' e não pode ser cancelado por aqui; abra um chamado."
                )
            for linha in pedido["itens"]:
                self._livro(linha["livro_id"])["estoque"] += linha["quantidade"]
            pedido["status"] = "cancelado"
            self.salvar()
        return {"ok": True, "pedido_id": pedido_id, "status": "cancelado"}

    # ------------------------------------------------------------- cobrança
    def _link(self, pedido: dict) -> str:
        # Simulado: troque pelo link do seu meio de pagamento (M-Pesa, e-Mola, banco, cartão).
        return f"https://pagar.exemplo.com/{pedido['id']}"

    def consultar_pendencias(self, telefone: str) -> list[dict]:
        hoje = self.relogio().date()
        pendentes = []
        for p in self.consultar_pedidos(telefone):
            if p["status"] in ("aguardando_pagamento", "pagamento_em_verificacao"):
                atraso = (hoje - date.fromisoformat(p["vencimento"])).days
                pendentes.append({"pedido_id": p["id"], "total": p["total"], "status": p["status"],
                                  "vencimento": p["vencimento"], "dias_em_atraso": max(atraso, 0)})
        return pendentes

    def gerar_link_pagamento(self, telefone: str, pedido_id: str) -> dict:
        pedido = self._pedido(telefone, pedido_id)
        if pedido["status"] != "aguardando_pagamento":
            raise ErroLoja(f"O pedido está '{pedido['status']}', não há pagamento a fazer.")
        return {"pedido_id": pedido_id, "total": pedido["total"], "link_pagamento": self._link(pedido)}

    def informar_pagamento(self, telefone: str, pedido_id: str, detalhes: str) -> dict:
        """O cliente diz que pagou. Nunca damos baixa só pela palavra dele: fica em verificação."""
        with self._trava:
            pedido = self._pedido(telefone, pedido_id)
            if pedido["status"] != "aguardando_pagamento":
                raise ErroLoja(f"O pedido está '{pedido['status']}'.")
            pedido["status"] = "pagamento_em_verificacao"
            pedido["pagamento_informado"] = detalhes
            self.salvar()
        return {"ok": True, "status": "pagamento_em_verificacao",
                "aviso": "A equipe confirma o pagamento em até 1 dia útil."}

    # ---------------------------------------------------------- agendamento
    def _vagas(self, inicio: datetime) -> int:
        ocupadas = sum(1 for a in self.dados["agendamentos"]
                       if a["status"] == "confirmado" and a["data_hora"] == inicio.isoformat(timespec="minutes"))
        return VAGAS_POR_HORARIO - ocupadas

    def horarios_disponiveis(self, dia: str) -> dict:
        try:
            data = date.fromisoformat(dia)
        except ValueError:
            raise ErroLoja("Use a data no formato AAAA-MM-DD.") from None
        momento = self.relogio()
        if data < momento.date():
            raise ErroLoja("Essa data já passou.")
        if data.weekday() not in DIAS_ABERTOS:
            return {"data": dia, "livres": [], "aviso": "A loja não abre aos domingos."}
        livres = []
        for hora in HORARIOS:
            inicio = datetime(data.year, data.month, data.day, hora, tzinfo=FUSO)
            if inicio > momento and self._vagas(inicio) > 0:
                livres.append(f"{hora:02d}:00")
        return {"data": dia, "livres": livres}

    def agendar(self, telefone: str, tipo: str, data_hora: str, observacao: str | None) -> dict:
        if tipo not in TIPOS_AGENDAMENTO:
            raise ErroLoja(f"Tipo inválido. Use um destes: {', '.join(TIPOS_AGENDAMENTO)}.")
        try:
            inicio = datetime.fromisoformat(data_hora).replace(tzinfo=FUSO, minute=0, second=0, microsecond=0)
        except ValueError:
            raise ErroLoja("Use data e hora no formato AAAA-MM-DDTHH:00.") from None
        if inicio <= self.relogio():
            raise ErroLoja("Esse horário já passou.")
        if inicio.weekday() not in DIAS_ABERTOS or inicio.hour not in HORARIOS:
            raise ErroLoja("Fora do horário de atendimento (seg a sáb, 9h às 18h).")
        with self._trava:
            if self._vagas(inicio) <= 0:
                raise ErroLoja("Esse horário está lotado; ofereça outro.")
            ag = {"id": _novo_id("AG"), "telefone": telefone, "tipo": tipo,
                  "descricao": TIPOS_AGENDAMENTO[tipo], "data_hora": inicio.isoformat(timespec="minutes"),
                  "observacao": observacao, "status": "confirmado"}
            self.dados["agendamentos"].append(ag)
            self.salvar()
        return ag

    def listar_agendamentos(self, telefone: str) -> list[dict]:
        return [a for a in self.dados["agendamentos"] if a["telefone"] == telefone and a["status"] == "confirmado"]

    def cancelar_agendamento(self, telefone: str, agendamento_id: str) -> dict:
        with self._trava:
            for a in self.dados["agendamentos"]:
                if a["id"] == agendamento_id and a["telefone"] == telefone and a["status"] == "confirmado":
                    a["status"] = "cancelado"
                    self.salvar()
                    return {"ok": True, "agendamento_id": agendamento_id, "status": "cancelado"}
        raise ErroLoja(f"Não encontrei o agendamento {agendamento_id} ativo para este cliente.")

    # ------------------------------------------------- suporte e pós-venda
    def abrir_chamado(self, telefone: str, assunto: str, descricao: str, pedido_id: str | None) -> dict:
        if pedido_id:
            self._pedido(telefone, pedido_id)
        with self._trava:
            chamado = {"id": _novo_id("CH"), "telefone": telefone, "pedido_id": pedido_id, "assunto": assunto,
                       "descricao": descricao, "status": "aberto",
                       "criado_em": self.relogio().isoformat(timespec="minutes")}
            self.dados["chamados"].append(chamado)
            self.salvar()
        return {**chamado, "prazo_resposta": "até 1 dia útil"}

    def registrar_avaliacao(self, telefone: str, pedido_id: str, nota: int, comentario: str | None) -> dict:
        if not 1 <= nota <= 5:
            raise ErroLoja("A nota vai de 1 a 5.")
        self._pedido(telefone, pedido_id)
        with self._trava:
            self.dados["avaliacoes"].append({"telefone": telefone, "pedido_id": pedido_id, "nota": nota,
                                             "comentario": comentario,
                                             "em": self.relogio().isoformat(timespec="minutes")})
            self.salvar()
        return {"ok": True}

    def pedir_humano(self, telefone: str, motivo: str) -> dict:
        with self._trava:
            self.dados["fila_humana"].append({"telefone": telefone, "motivo": motivo,
                                              "em": self.relogio().isoformat(timespec="minutes")})
            self.salvar()
        return {"ok": True, "aviso": "Um atendente da equipe vai continuar esta conversa."}

    # --------------------------------------------- tarefas proativas (lembretes)
    def pedidos_para_cobrar(self) -> list[dict]:
        """Pedidos vencidos e não pagos, até 3 lembretes, no máximo um por dia."""
        hoje = self.relogio().date()
        saida = []
        for p in self.dados["pedidos"]:
            if p["status"] != "aguardando_pagamento" or p["lembretes_cobranca"] >= 3:
                continue
            if date.fromisoformat(p["vencimento"]) > hoje or p.get("ultimo_lembrete") == hoje.isoformat():
                continue
            saida.append(p)
        return saida

    def pedidos_para_pos_venda(self, dias_apos_entrega: int = 3) -> list[dict]:
        hoje = self.relogio().date()
        return [p for p in self.dados["pedidos"]
                if p["status"] == "entregue" and not p["pos_venda_enviado"] and p["entregue_em"]
                and (hoje - date.fromisoformat(p["entregue_em"][:10])).days >= dias_apos_entrega]

    def marcar_lembrete(self, pedido_id: str, tipo: str) -> None:
        with self._trava:
            for p in self.dados["pedidos"]:
                if p["id"] == pedido_id:
                    if tipo == "cobranca":
                        p["lembretes_cobranca"] += 1
                        p["ultimo_lembrete"] = self.relogio().date().isoformat()
                    else:
                        p["pos_venda_enviado"] = True
            self.salvar()

    def link_pagamento(self, pedido: dict) -> str:
        return self._link(pedido)

    # ------------------------------------------- funções da equipe (assistente interno)
    def estoque_baixo(self, limite: int) -> list[dict]:
        """Produtos à venda (com preço) com stock no limite ou abaixo; no máximo 60, os mais vendáveis primeiro."""
        baixos = [{k: l.get(k) for k in ("id", "titulo", "genero", "estoque", "preco")}
                  for l in self.dados["livros"] if l.get("preco") and l["estoque"] <= limite]
        baixos.sort(key=lambda l: (l["estoque"], -l["preco"]))
        return baixos[:60] + ([{"aviso": f"Mais {len(baixos) - 60} produto(s) na mesma situação."}]
                              if len(baixos) > 60 else [])

    def cadastrar_livro(self, titulo: str, autor: str, genero: str, preco: float, estoque: int,
                        sinopse: str) -> dict:
        if preco <= 0 or estoque < 0:
            raise ErroLoja("Preço deve ser positivo e estoque não pode ser negativo.")
        with self._trava:
            if any(l["titulo"].lower() == titulo.lower() and l["autor"].lower() == autor.lower()
                   for l in self.dados["livros"]):
                raise ErroLoja("Esse livro já está no catálogo; use ajustar_estoque.")
            numero = 1 + sum(1 for l in self.dados["livros"] if str(l["id"]).startswith("NOVO-"))
            livro = {"id": f"NOVO-{numero:04d}", "titulo": titulo, "autor": autor, "genero": genero,
                     "preco": round(preco, 2), "estoque": estoque, "sinopse": sinopse}
            self.dados["livros"].append(livro)
            self.salvar()
        return livro

    def ajustar_estoque(self, livro_id: str, estoque: int, preco: float | None) -> dict:
        if estoque < 0:
            raise ErroLoja("Estoque não pode ser negativo.")
        with self._trava:
            livro = self._livro(livro_id)
            anterior = {"estoque": livro["estoque"], "preco": livro["preco"]}
            livro["estoque"] = estoque
            if preco is not None:
                livro["preco"] = round(preco, 2)
            self.salvar()
        return {"ok": True, "livro_id": livro_id, "antes": anterior,
                "agora": {"estoque": livro["estoque"], "preco": livro["preco"]}}

    def resumo_operacao(self, dias: int) -> dict:
        """Pedidos do WhatsApp, cobranças, agendamentos e atendimentos dos últimos dias."""
        desde = (self.relogio() - timedelta(days=dias)).isoformat(timespec="minutes")
        hoje = self.relogio().date().isoformat()
        pedidos = [p for p in self.dados["pedidos"] if p["criado_em"] >= desde[:16]]
        pagos = [p for p in self.dados["pedidos"]
                 if (p.get("pagamento") or {}).get("confirmado_em", "") >= desde[:16]]
        return {
            "periodo_dias": dias,
            "pedidos_novos": len(pedidos),
            "pedidos_pagos": len(pagos),
            "valor_pago": round(sum(p["total"] for p in pagos), 2),
            "aguardando_pagamento": [{"id": p["id"], "total": p["total"], "vencimento": p["vencimento"]}
                                     for p in self.dados["pedidos"] if p["status"] == "aguardando_pagamento"],
            "pagamentos_para_conferir": [p["id"] for p in self.dados["pedidos"]
                                         if p["status"] == "pagamento_em_verificacao"],
            "agendamentos_de_hoje_em_diante": [a for a in self.dados["agendamentos"]
                                               if a["status"] == "confirmado" and a["data_hora"][:10] >= hoje],
            "chamados_abertos": [c for c in self.dados["chamados"] if c["status"] == "aberto"],
            "pedidos_de_atendente": [h for h in self.dados["fila_humana"] if h["em"] >= desde[:16]],
            "avaliacoes_recentes": [a for a in self.dados["avaliacoes"] if a["em"] >= desde[:16]],
            "contactos_novos": sum(1 for em in self.dados["contatos"].values() if em >= desde[:16]),
            "pedidos_de_oracao": [o for o in self.dados["pedidos_oracao"] if o["em"] >= desde[:16]],
            "tarefas_pendentes": self.listar_tarefas(None, True),
        }

    # --------------------------------------------------- contactos e pedidos de oração
    def registrar_contato(self, telefone: str) -> bool:
        """Marca o primeiro contacto do número. Devolve True se é um contacto novo."""
        with self._trava:
            if telefone in self.dados["contatos"]:
                return False
            self.dados["contatos"][telefone] = self.relogio().isoformat(timespec="minutes")
            self.salvar()
        return True

    def registrar_pedido_oracao(self, telefone: str, pedido: str) -> dict:
        with self._trava:
            self.dados["pedidos_oracao"].append({"telefone": telefone, "pedido": pedido,
                                                 "em": self.relogio().isoformat(timespec="minutes")})
            self.salvar()
        return {"ok": True, "aviso": "Pedido entregue à equipa, que vai orar por esta intenção."}

    # ---------------------------------------------------------------- tarefas
    def _nova_tarefa(self, descricao: str, responsavel: str | None, prazo: str | None, origem: str) -> dict:
        tarefa = {"id": _novo_id("TAR"), "descricao": descricao, "responsavel": responsavel, "prazo": prazo,
                  "origem": origem, "status": "pendente", "criada_em": self.relogio().isoformat(timespec="minutes"),
                  "concluida_em": None}
        self.dados["tarefas"].append(tarefa)
        return tarefa

    def criar_tarefa(self, descricao: str, responsavel: str | None, prazo: str | None) -> dict:
        if prazo:
            date.fromisoformat(prazo)
        with self._trava:
            tarefa = self._nova_tarefa(descricao.strip(), responsavel, prazo, "equipa")
            self.salvar()
        return tarefa

    def listar_tarefas(self, responsavel: str | None, so_pendentes: bool) -> list[dict]:
        return [t for t in self.dados["tarefas"]
                if (not so_pendentes or t["status"] == "pendente")
                and (responsavel is None or (t["responsavel"] or "").lower() == responsavel.lower())]

    def concluir_tarefa(self, tarefa_id: str) -> dict:
        with self._trava:
            for t in self.dados["tarefas"]:
                if t["id"] == tarefa_id:
                    t["status"] = "concluida"
                    t["concluida_em"] = self.relogio().isoformat(timespec="minutes")
                    self.salvar()
                    return {"ok": True, "tarefa": t}
        raise ErroLoja(f"Tarefa {tarefa_id} não existe.")

    def atribuir_tarefa(self, tarefa_id: str, responsavel: str) -> dict:
        with self._trava:
            for t in self.dados["tarefas"]:
                if t["id"] == tarefa_id:
                    t["responsavel"] = responsavel
                    self.salvar()
                    return {"ok": True, "tarefa": t}
        raise ErroLoja(f"Tarefa {tarefa_id} não existe.")

    # ------------------------------------------------- pedidos (lado da equipa)
    def _pedido_por_id(self, pedido_id: str) -> dict:
        for p in self.dados["pedidos"]:
            if p["id"] == pedido_id:
                return p
        raise ErroLoja(f"Pedido {pedido_id} não existe.")

    def confirmar_pagamento(self, pedido_id: str, forma: str, referencia: str | None) -> dict:
        """A equipa confirmou que o dinheiro entrou (M-Pesa, e-Mola, banco, cartão, numerário)."""
        with self._trava:
            p = self._pedido_por_id(pedido_id)
            if p["status"] not in ("aguardando_pagamento", "pagamento_em_verificacao"):
                raise ErroLoja(f"O pedido está '{p['status']}'.")
            p["status"] = "pago"
            p["pagamento"] = {"forma": forma, "referencia": referencia,
                              "confirmado_em": self.relogio().isoformat(timespec="minutes")}
            self._nova_tarefa(f"Pedido {pedido_id} pago: embalar e "
                              f"{'enviar ao cliente' if p['entrega'] == 'envio' else 'deixar pronto para levantamento'}",
                              None, None, "pedido")
            self.salvar()
        return {"ok": True, "pedido": p}

    def atualizar_estado_pedido(self, pedido_id: str, estado: str) -> dict:
        ordem = ["pago", "enviado", "entregue"]
        with self._trava:
            p = self._pedido_por_id(pedido_id)
            if estado not in ("enviado", "entregue") or p["status"] not in ordem or \
                    ordem.index(estado) <= ordem.index(p["status"]):
                raise ErroLoja(f"Não dá para passar de '{p['status']}' para '{estado}'.")
            p["status"] = estado
            if estado == "entregue":
                p["entregue_em"] = self.relogio().isoformat(timespec="minutes")
            self.salvar()
        return {"ok": True, "pedido_id": pedido_id, "status": estado}

