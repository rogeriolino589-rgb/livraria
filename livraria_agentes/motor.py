"""Motor da conversa: recebe a mensagem do cliente, roda o agente ativo com o
Claude e as ferramentas, e devolve as mensagens de resposta.

O histórico de cada cliente fica em um arquivo JSON por número de WhatsApp.
O histórico só cresce (nunca é editado), o que mantém o cache do prompt e o
raciocínio do modelo válidos entre uma mensagem e outra.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import anthropic

from . import ferramentas
from .agentes import AGENTE_INICIAL, AGENTES, SISTEMA
from .loja import ErroLoja, Loja

log = logging.getLogger(__name__)

MODELO = os.environ.get("LIVRARIA_MODELO", "claude-opus-5-5")
ESFORCO = os.environ.get("LIVRARIA_ESFORCO", "medium")  # low | medium | high
MAX_PASSOS = 12  # chamadas ao modelo por mensagem do cliente
BETA_FALLBACK = "server-side-fallback-2026-07-01"

DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]

MSG_INSTABILIDADE = "Desculpe, tivemos uma falha técnica. Pode enviar a sua mensagem de novo dentro de instantes? 🙏"
MSG_RECUSA = "Desculpe, não consigo ajudar com isso por aqui. Posso ajudar com livros, pedidos ou marcações?"


@dataclass
class Resposta:
    textos: list[str] = field(default_factory=list)
    agente: str = AGENTE_INICIAL
    aguardando_humano: bool = False


class Motor:
    def __init__(self, loja: Loja, pasta_conversas: Path, cliente: anthropic.Anthropic | None = None):
        self.loja = loja
        self.pasta = Path(pasta_conversas)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self._cliente = cliente

    @property
    def cliente(self) -> anthropic.Anthropic:
        if self._cliente is None:
            self._cliente = anthropic.Anthropic()
        return self._cliente

    # ------------------------------------------------------------ estado
    def _arquivo(self, telefone: str) -> Path:
        return self.pasta / f"{''.join(c for c in telefone if c.isdigit())}.json"

    def carregar(self, telefone: str) -> dict:
        arq = self._arquivo(telefone)
        if arq.exists():
            return json.loads(arq.read_text(encoding="utf-8"))
        return {"telefone": telefone, "agente": AGENTE_INICIAL, "mensagens": [], "contexto_em": None,
                "avisos_pendentes": [], "aguardando_humano": False}

    def salvar(self, estado: dict) -> None:
        arq = self._arquivo(estado["telefone"])
        temp = arq.with_suffix(".tmp")
        temp.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
        temp.replace(arq)

    def reiniciar(self, telefone: str) -> None:
        self._arquivo(telefone).unlink(missing_ok=True)

    def notificar(self, telefone: str, texto: str, agente: str) -> None:
        """Registra uma mensagem automática que a loja enviou ao cliente (lembrete de cobrança,
        pós-venda). Quando o cliente responder, o agente indicado assume já sabendo do envio."""
        estado = self.carregar(telefone)
        estado["agente"] = agente
        estado["avisos_pendentes"].append(
            f"Antes da mensagem acima, a loja enviou automaticamente ao cliente esta mensagem: «{texto}». "
            f"Agente ativo: {agente}.")
        self.salvar(estado)

    def registrar_resposta_humana(self, telefone: str, texto: str) -> None:
        estado = self.carregar(telefone)
        estado["conversa_humana"] = estado.get("conversa_humana", []) + [f"Equipe: {texto}"]
        self.salvar(estado)

    def liberar_humano(self, telefone: str) -> None:
        """A equipe terminou o atendimento: o robô volta a responder este cliente."""
        estado = self.carregar(telefone)
        estado["aguardando_humano"] = False
        conversa = estado.pop("conversa_humana", [])
        aviso = "Um atendente humano conversou com o cliente e devolveu o atendimento para os agentes."
        if conversa:
            aviso += " Conversa nesse período: " + " | ".join(f"«{m}»" for m in conversa)
        estado["avisos_pendentes"].append(aviso)
        self.salvar(estado)

    # ----------------------------------------------------------- conversa
    def responder(self, telefone: str, texto: str) -> Resposta:
        estado = self.carregar(telefone)
        if estado["aguardando_humano"]:
            # Um atendente está cuidando da conversa: o robô fica quieto e só registra.
            self.loja.pedir_humano(telefone, f"Nova mensagem do cliente: {texto}")
            estado["conversa_humana"] = estado.get("conversa_humana", []) + [f"Cliente: {texto}"]
            self.salvar(estado)
            return Resposta([], estado["agente"], True)

        msgs: list[dict] = estado["mensagens"]
        avisos = self._retirar_sistema_na_cauda(msgs)
        if not msgs:
            avisos.append(f"Agente ativo: {estado['agente']}.")
        momento = self.loja.relogio()
        if estado["contexto_em"] != momento.date().isoformat():
            nome = self.loja.nome_cliente(telefone) or "ainda não informado"
            dia = DIAS_SEMANA[momento.weekday()]
            avisos.append(f"Contexto: agora é {dia}, {momento:%d/%m/%Y %H:%M} (hora de Moçambique). "
                          f"Cliente: nome {nome}; WhatsApp {telefone}.")
            estado["contexto_em"] = momento.date().isoformat()
        avisos += estado["avisos_pendentes"]
        estado["avisos_pendentes"] = []

        msgs.append({"role": "user", "content": texto})
        if avisos:
            msgs.append({"role": "system", "content": "\n".join(avisos)})

        resposta = Resposta(agente=estado["agente"])
        try:
            self._rodar(estado, resposta)
        except anthropic.APIError as erro:
            log.exception("Falha na API do Claude: %s", erro)
            resposta.textos.append(MSG_INSTABILIDADE)
        # Outros erros (ex.: chave da API ausente) sobem sem salvar a conversa.
        resposta.agente = estado["agente"]
        resposta.aguardando_humano = estado["aguardando_humano"]
        self.salvar(estado)
        return resposta

    def _retirar_sistema_na_cauda(self, msgs: list[dict]) -> list[str]:
        """Uma mensagem de sistema não pode vir antes da mensagem do cliente. Se a última chamada
        falhou logo depois de uma, ela é movida para depois da nova mensagem do cliente."""
        textos = []
        while msgs and msgs[-1]["role"] == "system":
            textos.insert(0, msgs.pop()["content"])
        return textos

    def _chamar(self, msgs: list[dict]):
        return self.cliente.beta.messages.create(
            model=MODELO,
            max_tokens=16000,
            system=[{"type": "text", "text": SISTEMA, "cache_control": {"type": "ephemeral"}}],
            tools=ferramentas.FERRAMENTAS,
            messages=msgs,
            output_config={"effort": ESFORCO},
            cache_control={"type": "ephemeral"},
            betas=[BETA_FALLBACK],
            fallbacks="default",  # se o modelo recusar, a API tenta de novo com outro modelo
        )

    def _rodar(self, estado: dict, resposta: Resposta) -> None:
        msgs = estado["mensagens"]
        telefone = estado["telefone"]
        for _ in range(MAX_PASSOS):
            r = self._chamar(msgs)
            conteudo = [b.model_dump(mode="json", exclude_none=True) for b in r.content]
            if not conteudo:
                conteudo = [{"type": "text", "text": MSG_RECUSA if r.stop_reason == "refusal" else "..."}]
            msgs.append({"role": "assistant", "content": conteudo})
            resposta.textos += [b.text.strip() for b in r.content if b.type == "text" and b.text.strip()]

            if r.stop_reason == "pause_turn":
                continue
            if r.stop_reason == "refusal":
                resposta.textos.append(MSG_RECUSA)
                return
            if r.stop_reason == "max_tokens":
                log.warning("Resposta cortada por max_tokens (%s)", telefone)
                return
            if r.stop_reason != "tool_use":
                return

            resultados, novo_agente, motivo = [], None, ""
            agente = estado["agente"]
            for bloco in r.content:
                if bloco.type != "tool_use":
                    continue
                saida, erro = self._executar(estado, agente, bloco.name, bloco.input)
                if bloco.name == "transferir_agente" and not erro:
                    novo_agente, motivo = bloco.input["agente"], bloco.input["motivo"]
                resultados.append({"type": "tool_result", "tool_use_id": bloco.id, "content": saida,
                                   **({"is_error": True} if erro else {})})
            msgs.append({"role": "user", "content": resultados})
            if novo_agente:
                estado["agente"] = novo_agente
                msgs.append({"role": "system", "content":
                             f"Agente ativo agora: {novo_agente}. Motivo da transferência: {motivo} "
                             f"Continue o atendimento a partir daqui."})
        log.warning("Limite de passos atingido (%s)", telefone)
        resposta.textos.append("Só um instante, vou verificar isso com a equipa.")

    def _executar(self, estado: dict, agente: str, nome: str, entrada: dict) -> tuple[str, bool]:
        """Devolve (conteúdo do resultado, se é erro)."""
        if nome not in ferramentas.NOMES:
            return f"Ferramenta desconhecida: {nome}", True
        if nome not in AGENTES[agente]["ferramentas"]:
            return (f"A ferramenta {nome} não é do agente {agente}. "
                    f"Use transferir_agente para passar a conversa ao agente certo."), True
        if nome == "transferir_agente":
            if entrada.get("agente") not in AGENTES:
                return "Agente inválido.", True
            if entrada["agente"] == agente:
                return "Você já é esse agente; continue o atendimento.", True
            return json.dumps({"ok": True}), False
        try:
            saida = ferramentas.executar(self.loja, estado["telefone"], nome, entrada)
        except ErroLoja as erro:
            return str(erro), True
        except (KeyError, TypeError, ValueError) as erro:
            log.exception("Entrada inválida em %s", nome)
            return f"Entrada inválida para {nome}: {erro}", True
        if nome == "chamar_humano":
            estado["aguardando_humano"] = True
        return saida, False
