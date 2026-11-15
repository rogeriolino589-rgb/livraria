# Livraria: agentes de IA para WhatsApp

Agentes de atendimento feitos com o Claude (modelo Claude Opus 5.5) para uma livraria. Por enquanto a
conversa é simulada no terminal; a ligação com o WhatsApp vem depois.

| Agente | O que faz |
|---|---|
| **Atendimento e Vendas** | Recebe o cliente, recomenda livros do catálogo, cria o pedido e envia o link de pagamento |
| **Agendamento** | Marca, consulta e cancela horários na loja (retirada, consultoria de leitura, clube do livro) |
| **Cobrança** | Reenvia links de pagamento, registra "já paguei" (fica em verificação), cancela se o cliente desistir |
| **Suporte e Pós-venda** | Abre chamados (atraso, troca, defeito), pede avaliação depois da entrega |

Os agentes passam a conversa entre si sozinhos ("tudo num único fluxo") e podem chamar um atendente
humano. Cada cliente só enxerga os próprios pedidos e agendamentos.

## Como usar

```bash
pip install -e .
export ANTHROPIC_API_KEY=sua-chave        # crie em https://platform.claude.com
python -m livraria_agentes.chat --telefone 5511900000001
```

Comandos no chat: `/agente` (mostra o agente ativo), `/reiniciar`, `/sair`.

Clientes de exemplo: `5511900000001` (Ana, com um pedido vencido) e `5511900000002` (Bruno, com um
pedido entregue). Qualquer outro número é um cliente novo.

### Mensagens automáticas (cobrança e pós-venda)

```bash
python -m livraria_agentes.lembretes
```

Envia lembrete de pagamento para pedidos vencidos (até 3, um por dia) e pergunta a opinião de quem recebeu
o pedido há 3 dias ou mais. Quando o cliente responde, o agente certo continua a conversa. Rode uma vez por
dia (por exemplo com `cron`).

## Personalizar

- **Nome, tom de voz e políticas da loja:** `livraria_agentes/agentes.py`
- **Catálogo e dados de exemplo:** `dados/loja_inicial.json` (copiado para `dados/estado/` no primeiro uso)
- **Link de pagamento:** `Loja._link` em `livraria_agentes/loja.py` (hoje é um link de exemplo)
- **Esforço do modelo:** variável `LIVRARIA_ESFORCO` (`low`, `medium` ou `high`; padrão `medium`)

## Ligar no WhatsApp (próximo passo)

Use a API oficial do WhatsApp Business (Cloud API da Meta): um servidor recebe as mensagens (webhook),
chama `Motor.responder(telefone, texto)` e envia as respostas. Ferramentas que conectam o WhatsApp por
QR Code (WhatsApp Web) vão contra os termos do WhatsApp e podem fazer o número ser banido.

## Testes

```bash
pip install -e '.[dev]'
pytest
```

Os testes não chamam a API: usam respostas simuladas do Claude.
