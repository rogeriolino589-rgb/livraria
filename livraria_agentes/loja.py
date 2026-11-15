"""Dados e regras de negócio da livraria.

Tudo fica num arquivo JSON simples. Cada operação recebe o telefone do
cliente da conversa: um cliente nunca enxerga pedidos, cobranças ou
agendamentos de outra pessoa, mesmo que peça.
"""

from __future__ import annotations

import json
import secrets
import shutil
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")
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
FRETE_FIXO = 15.0


class ErroLoja(Exception):
    """Erro de regra de negócio, com mensagem para o agente repassar."""


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

    def registrar_cliente(self, telefone: str, nome: str) -> dict:
        nome = nome.strip()
        if not nome:
            raise ErroLoja("Informe o nome do cliente.")
        with self._trava:
            self.dados["clientes"].setdefault(telefone, {})["nome"] = nome
            self.salvar()
        return {"ok": True, "nome": nome}

    # ------------------------------------------------------------- catálogo
    def buscar_livros(self, consulta: str, genero: str | None, preco_max: float | None) -> list[dict]:
        termos = [t for t in consulta.lower().split() if len(t) > 2]
        achados = []
        for livro in self.dados["livros"]:
            if genero and genero.lower() not in livro["genero"].lower():
                continue
            if preco_max is not None and livro["preco"] > preco_max:
                continue
            texto = " ".join([livro["titulo"], livro["autor"], livro["genero"], livro["sinopse"]]).lower()
            pontos = sum(1 for t in termos if t in texto)
            if termos and pontos == 0:
                continue
            achados.append((pontos, livro))
        achados.sort(key=lambda par: (-par[0], par[1]["titulo"]))
        return [
            {k: livro[k] for k in ("id", "titulo", "autor", "genero", "preco", "estoque")}
            for _, livro in achados[:8]
        ]

    def detalhes_livro(self, livro_id: str) -> dict:
        return dict(self._livro(livro_id))

    # -------------------------------------------------------------- pedidos
    def criar_pedido(self, telefone: str, itens: list[dict], entrega: str) -> dict:
        if not itens:
            raise ErroLoja("O pedido precisa de pelo menos um livro.")
        if entrega not in ("retirada", "envio"):
            raise ErroLoja("Entrega deve ser 'retirada' ou 'envio'.")
        if not self.nome_cliente(telefone):
            raise ErroLoja("Registre o nome do cliente (registrar_cliente) antes de criar o pedido.")
        with self._trava:
            linhas, subtotal = [], 0.0
            for item in itens:
                livro = self._livro(item["livro_id"])
                qtd = int(item["quantidade"])
                if qtd < 1:
                    raise ErroLoja("Quantidade deve ser pelo menos 1.")
                if livro["estoque"] < qtd:
                    raise ErroLoja(f"Só há {livro['estoque']} unidade(s) de '{livro['titulo']}' em estoque.")
                linhas.append({"livro_id": livro["id"], "titulo": livro["titulo"], "quantidade": qtd,
                               "preco_unitario": livro["preco"]})
                subtotal += livro["preco"] * qtd
            for linha in linhas:
                self._livro(linha["livro_id"])["estoque"] -= linha["quantidade"]
            frete = FRETE_FIXO if entrega == "envio" else 0.0
            momento = self.relogio()
            pedido = {
                "id": _novo_id("PED"),
                "telefone": telefone,
                "itens": linhas,
                "entrega": entrega,
                "frete": frete,
                "total": round(subtotal + frete, 2),
                "status": "aguardando_pagamento",
                "criado_em": momento.isoformat(timespec="minutes"),
                "vencimento": (momento.date() + timedelta(days=PRAZO_PAGAMENTO_DIAS)).isoformat(),
                "entregue_em": None,
                "lembretes_cobranca": 0,
                "pos_venda_enviado": False,
            }
            self.dados["pedidos"].append(pedido)
            self.salvar()
        return {**pedido, "link_pagamento": self._link(pedido)}

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
        # Simulado: troque pelo link do seu meio de pagamento (Pix, Mercado Pago...).
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
