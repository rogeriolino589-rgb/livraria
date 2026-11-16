# CPAD Moçambique: robô de atendimento e operação

Agentes de atendimento feitos com o Claude (modelo Claude Opus 5.5) para uma livraria em Moçambique
(valores em meticais, hora de Maputo, números +258, pagamentos por M-Pesa, e-Mola, banco ou cartão). Por enquanto a
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
python -m livraria_agentes.chat --telefone 258840000001
```

Comandos no chat: `/agente` (mostra o agente ativo), `/reiniciar`, `/sair`.

Clientes de exemplo: `258840000001` (Ana, com um pedido vencido) e `258840000002` (Bruno, com um
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

## Ligar no WhatsApp (API oficial da Meta)

O servidor `livraria_agentes/servidor.py` recebe as mensagens do WhatsApp (webhook), passa para os
agentes e envia as respostas. Ferramentas que conectam o WhatsApp por QR Code (WhatsApp Web) vão contra
os termos do WhatsApp e podem fazer o número ser banido; aqui usamos só a API oficial.

### 1. Na Meta
1. Em developers.facebook.com, crie um app do tipo **Empresa** e adicione o produto **WhatsApp**.
2. Em **WhatsApp > Configuração da API**, anote o **Phone number ID** e o **token** (o temporário dura
   24h; para produção, gere um permanente em Business Manager > Usuários do sistema).
3. Cadastre seu celular como destinatário de teste.
4. Em **Configurações do app > Básico**, anote a **Chave secreta do app**.

### 2. Suba o servidor
Ele precisa de um endereço HTTPS público. Qualquer serviço que rode Docker serve (Render, Railway, Fly.io,
uma VPS). Monte um **disco persistente** em `/dados`, senão pedidos e conversas somem a cada deploy.

Variáveis de ambiente:

| Variável | O que é |
|---|---|
| `ANTHROPIC_API_KEY` | Chave da API do Claude |
| `WHATSAPP_TOKEN` | Token de acesso da Meta |
| `WHATSAPP_PHONE_NUMBER_ID` | Id do número do WhatsApp |
| `WHATSAPP_VERIFY_TOKEN` | Uma senha que você inventa (usada no passo 3) |
| `WHATSAPP_APP_SECRET` | Chave secreta do app (valida que as mensagens vêm mesmo da Meta) |

Para testar no seu computador: `python -m livraria_agentes.servidor` e exponha a porta 8000 com um túnel
HTTPS (por exemplo `cloudflared tunnel --url http://localhost:8000`).

### 3. Ligue o webhook
Em **WhatsApp > Configuração**, coloque a URL de callback `https://SEU-ENDERECO/webhook`, o mesmo
`WHATSAPP_VERIFY_TOKEN`, e assine o campo **messages**. Mande "oi" do seu celular para o número de teste.

### 4. Modelos de mensagem (para os lembretes)
Em **WhatsApp Manager > Modelos de mensagem**, crie em português (pt_PT), categoria **Utilidade**, os
modelos `lembrete_pagamento` e `pos_venda` com os textos de `MODELOS` em `livraria_agentes/lembretes.py`.
Depois de aprovados: `python -m livraria_agentes.lembretes --whatsapp` (uma vez por dia).

### Atendimento humano
Quando um agente chama um atendente, o robô para de responder aquele cliente.

```bash
python -m livraria_agentes.equipe fila                         # quem está esperando
python -m livraria_agentes.equipe responder 25884... "Oi! Aqui é a Júlia, da livraria."
python -m livraria_agentes.equipe liberar 25884...              # o robô volta a atender
```

## Assistente interno (equipe da livraria)

Um assistente separado, só para a equipe, que conversa pelo terminal ou pelo WhatsApp (números em
`EQUIPE_WHATSAPP`). Ele:

- **Lê, resume e extrai documentos dos e-mails** por IMAP: copia anexos (e o próprio e-mail, se pedirem)
  para o arquivo da livraria, organizado por mês e remetente, sem duplicar. Lê o texto de PDF, planilhas,
  XML e CSV. Não envia, não apaga e não move e-mails.
- **Registra faturas, recibos e comprovantes** encontrados nos e-mails, procura o documento
  correspondente nos ERPs e extrai a tabela de faturas para planilha Excel.
- **Junta o ERP19 (2016 a julho/2022) e o ERP22 (agosto/2022 até hoje) numa história única**: importa os
  relatórios exportados (`.xlsx` ou `.csv`), calcula vendas por dia, mês, ano, vendedor, província e
  cliente e o número de documentos por dia, e confere a história (meses sem dados, documentos fora do
  período do seu sistema, números repetidos nos dois ERPs, a passagem de julho para agosto de 2022).
- **Exporta tudo consolidado para o superapp** (arquivo JSON; envio automático quando `SUPERAPP_URL`
  estiver definida).
- Cuida de **estoque e catálogo**, escreve **rascunhos de posts** para as redes sociais e **pesquisa na web**.
- Faz um **resumo diário** para a equipe.

Ações que mudam dados (cadastrar livro, mudar estoque, enviar ao superapp) só acontecem com pedido e
confirmação da equipe na conversa. Instruções que venham dentro de e-mails ou sites são ignoradas.

```bash
python -m livraria_agentes.interno.chat --nome Rogério      # chat no terminal
python -m livraria_agentes.interno.resumo_diario            # resumo do dia (--whatsapp para enviar)
```

Relatórios dos ERPs: coloque os arquivos exportados em `dados/entrada/erp19/` e `dados/entrada/erp22/` e
peça "importe os relatórios novos" (ou use `/importar arquivo.xlsx erp19` no chat). Se as colunas não forem
reconhecidas, copie `config/erps.exemplo.json` para `config/erps.json` e escreva os nomes das colunas.

| Variável | O que é |
|---|---|
| `IMAP_HOST`, `IMAP_PORTA`, `IMAP_USUARIO`, `IMAP_SENHA`, `IMAP_PASTA` | Caixa de e-mail (porta 993, pasta INBOX por padrão) |
| `EQUIPE_WHATSAPP` | Números da equipe, ex.: `258840000010:Rogério,258840000011:Ana` |
| `SUPERAPP_URL`, `SUPERAPP_TOKEN` | Endereço e token do superapp (opcional) |
| `ARQUIVO_DOCUMENTOS` | Pasta onde os documentos copiados dos e-mails são guardados |
| `LIVRARIA_FUSO` | Fuso horário, ex.: `Africa/Maputo` (padrão) |

## Catálogo real da CPAD

```bash
python -m livraria_agentes.importar_catalogo "CPAD ERP Moçambique — Livraria.html"   # ou produtos.xlsx / .csv
```

Lê os 21.813 produtos do ERP da livraria (código, ISBN, título, categoria, preço em MT e stock) e substitui
o catálogo de exemplo. Produtos sem preço não são oferecidos a clientes. A busca ignora acentos e
maiúsculas ("bíblia" encontra "BIBLIA"). Alterações feitas dentro da página do ERP ficam só no navegador
onde foram feitas: para preços e stock atualizados, importe uma exportação recente em planilha.

## Clientes da CPAD

```bash
python -m livraria_agentes.importar_clientes "CPAD ERP Moçambique — Livraria.html"   # ou clientes.xlsx / .csv
```

Importa os 12.068 clientes do ERP (igrejas, pastores, missionários, revendedores, clientes VIP...). Os números
moçambicanos passam ao formato do WhatsApp; quando um cliente da lista escreve, os agentes já sabem o nome,
o tipo e a cidade. A equipa procura clientes e aniversariantes no assistente interno. São dados pessoais:
ficam só na base do robô (fora do Git), e mensagens de marketing só para quem aceitou receber.

## Descontos para instituições

Igrejas, empresas/instituições, revendedores (incluindo pastores revendedores) e livrarias registados no
cadastro, em compras a partir de **5.000 MT em produtos** (sem a taxa de entrega): **30% nos produtos da
marca CPAD** e **15% nos outros**. Produto CPAD = categoria "CPAD - ..." no ERP ou ISBN/código de barras da
CPAD (978-85-263, 7908234, 7898203). O sistema calcula sozinho no orçamento e no pedido; quem não está no
cadastro como instituição fala com um atendente. Ajustável em `loja.json` → `config` → `desconto_instituicoes`.

## O dia a dia da loja (os 7 trabalhos)

| Trabalho | Quem faz |
|---|---|
| Stock | Assistente interno: stock baixo, esgotados, cadastro e ajuste de livros |
| Vendas | Agentes do WhatsApp vendem e cobram; a equipa confirma o pagamento (`pedido_confirmar_pagamento`) |
| Redes sociais | Rascunhos e calendário para Instagram, Facebook, TikTok e Threads (publicação após ligar as contas) |
| WhatsApp 24h | Agentes de atendimento, vendas, marcações, cobrança, suporte e pedidos de oração |
| Equipa | Tarefas com responsável e prazo; cada pedido novo gera a tarefa de separar e, depois de pago, a de embalar |
| Financeiro | Entradas e saídas por categoria e forma de pagamento (M-Pesa, e-Mola, banco, cartão, numerário) |
| Relatórios | 7h30: tarefas para cada pessoa + resumo; 18h: relatório do dia para o responsável |

Pedidos de oração recebidos no WhatsApp são acolhidos sem oferta de venda e entram no relatório da noite.

### Agendar as rotinas

Linux/Mac (`crontab -e`, hora de Maputo):

```
30 7 * * *  cd /caminho/livraria && python -m livraria_agentes.interno.rotinas manha --whatsapp
0 18 * * *  cd /caminho/livraria && python -m livraria_agentes.interno.rotinas noite --whatsapp
0 9 * * *   cd /caminho/livraria && python -m livraria_agentes.lembretes --whatsapp
```

Windows: Agendador de Tarefas → Criar Tarefa Básica → Diariamente às 7:30 → Iniciar um programa →
`python` com argumentos `-m livraria_agentes.interno.rotinas manha --whatsapp` e "Iniciar em" a pasta do projeto.
Repita para as 18:00 com `noite`.

| Variável | O que é |
|---|---|
| `LOJA_NOME` | Nome da loja (padrão: CPAD Moçambique) |
| `LOJA_ENDERECO`, `LOJA_CONTACTOS` | Endereço e contactos oficiais, usados pelos agentes |
| `DONO_WHATSAPP` | Quem recebe o resumo da manhã e o relatório das 18h |

## Testes

```bash
pip install -e '.[dev]'
pytest
```

Os testes não chamam a API: usam respostas simuladas do Claude.
