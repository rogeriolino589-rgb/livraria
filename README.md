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

### Várias linhas de WhatsApp

Em Moçambique há uma linha (e um vendedor) por tipo de cliente: igrejas (+258 86 504 8400); empresas,
instituições, livrarias e revendedores (+258 84 508 2787); venda a retalho — clientes VIP, pastores e
missionários — (+258 84 468 9369) e atendimento internacional em inglês e francês (+258 87 712 7070).
Se várias linhas forem ligadas à mesma conta da Meta, o servidor responde sempre pelo número em que o cliente
escreveu, e os agentes indicam a linha certa conforme o tipo do cliente (`contactos_por_tipo` no perfil do país).

### Avisos aos vendedores

Cada linha corporativa tem um vendedor, em `config/vendedores.json`: igrejas — Damião Sebastião Cau
(+258 86 504 8400); empresas, instituições, revendedores e livrarias — Sérgio Paulo Fernando (+258 84 508 2787);
atendimento internacional — irmã Priscila Vilanculos (+258 87 712 7070); retalho — ainda sem vendedor. Os
vendedores usam só as linhas corporativas, e o aviso vai para a linha. O robô atende pelas próprias linhas
corporativas (`linhas_do_robo` no perfil do país), em coexistência com a app WhatsApp Business de cada vendedor:
o vendedor vê na app as conversas que o robô atendeu e continua nelas quando o robô passa o cliente para uma
pessoa. Nesse caso não há aviso por mensagem (um número não manda mensagem a si próprio); o vendedor recebe a
tarefa, que aparece na lista das 7h30. Ao ligar as linhas na Meta, use o registo de números já em uso na app
WhatsApp Business (coexistência). Quando o robô passa um cliente para uma pessoa, ou
quando entra um pedido, o vendedor da linha desse cliente recebe no WhatsApp: cliente, tipo, número (com link
wa.me), motivo ou total do pedido; e ganha uma tarefa em seu nome, que aparece na lista das 7h30. Se o vendedor
não falou com o número da loja nas últimas 24h, o aviso segue pelo modelo aprovado `aviso_vendedor`
(categoria Utilidade, pt_PT): "Olá, {{1}}! {{2}}: {{3}} ({{4}}). Os detalhes estão na sua lista de tarefas;
responda aqui para ver."

### Teste piloto: linha de retalho (+258 84 468 9369)

1. **Telemóvel da linha:** app WhatsApp Business atualizada (2.24.17 ou superior). Não apague nem
   desregiste o número da app.
2. **Meta:** conta Meta Business da CPAD (verificada) e app na Meta for Developers com o WhatsApp. Ligue a
   linha pelo registo de coexistência (*Embedded Signup*, opção "ligar uma conta existente da app WhatsApp
   Business") — diretamente ou através de um parceiro da Meta que ofereça coexistência. Durante o registo, o
   WhatsApp Web e outros aparelhos ligados são desligados; volte a ligá-los depois. O número fica em
   sincronização (sync_pending) até ficar ativo.
3. **Webhook:** assine os campos `messages` e `smb_message_echoes` (respostas que a equipa dá pela app).
4. **Servidor:** `LIVRARIA_PAIS=mz`, `WHATSAPP_NUMERO_ROBO="+258 84 468 9369"` (só esta linha fica ativa),
   `WHATSAPP_PHONE_NUMBER_ID` da linha de retalho, token, segredo do app, senha do webhook e
   `ANTHROPIC_API_KEY`. Importe o catálogo e os clientes (`importar_catalogo`, `importar_clientes`).
5. **Teste:** de um telemóvel pessoal, escreva para a linha e experimente: pedir uma Bíblia, pedir preço,
   fazer um pedido, pedir oração, pedir para falar com uma pessoa. Responda pela app para ver o robô calar-se,
   e escreva `#robo` para lhe devolver o cliente.

Durante o piloto, quem acompanhar a app da linha de retalho é quem atende os clientes passados a uma pessoa.

### Campanha progressiva de contacto

```bash
python -m livraria_agentes.campanha importar-leads "CPAD ERP Moçambique — Livraria.html"   # leads do Caçador
python -m livraria_agentes.campanha lote --html hoje.html    # lote do dia (o mesmo se já foi gerado)
python -m livraria_agentes.campanha progresso
```

Cada dia sai o lote seguinte da lista (cadastro primeiro, depois leads de prioridade alta, média e o resto), sem
repetir ninguém até completar. Cada contacto vai para a linha certa: em Moçambique, igrejas → Damião, empresas,
instituições, livrarias e revendedores → Sérgio, os restantes (e leads sem tipo) como Cliente VIP → retalho; fora
de Moçambique, linha internacional, mantendo a distinção igreja / instituição / VIP. Para cada um há um link
wa.me com a mensagem já escrita (português, inglês ou francês conforme o indicativo), com "responda SAIR". Quem
responde SAIR/STOP sai da lista para sempre. A página do dia está em `/campanha?chave=CAMPANHA_CHAVE` (e
`&linha=...` para uma só linha) e o link vai no resumo das 7h30. Limite por linha e países em `config/campanha.json`.

### Atendimento humano
Quando um agente chama um atendente, ou quando alguém da equipa responde ao cliente pela app WhatsApp Business
(coexistência), o robô para de responder aquele cliente. Para lhe devolver o cliente, escreva `#robo` na
conversa pela app (ou use `equipe liberar`); sem resposta humana durante 24h, o robô volta a atender.

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

## Vários países

Cada país tem um perfil em `config/paises/` e roda a sua própria instalação (dados, catálogo, clientes e
WhatsApp separados), escolhida com `LIVRARIA_PAIS`:

| Código | País | Moeda | Língua dos clientes | Estado |
|---|---|---|---|---|
| `mz` | Moçambique | MZN (MT) | português | em uso |
| `sz` | Eswatini | SZL (E) | inglês | rascunho a confirmar |
| `za` | África do Sul | ZAR (R) | inglês | rascunho a confirmar |
| `cd` | RD Congo | USD ($) | francês | rascunho a confirmar |
| `mu` | Ilhas Maurício | MUR (Rs) | inglês (e francês) | rascunho a confirmar |

O perfil define moeda e formato dos valores, fuso horário, línguas, indicativo e formato dos telemóveis,
formas de pagamento, taxa de entrega, imposto, identificação fiscal e o mínimo para o desconto de
instituições (sem mínimo definido, não há desconto automático). Os agentes respondem na língua em que o
cliente escreve; as mensagens fixas e os modelos do WhatsApp existem em português, inglês e francês. Os
pontos a confirmar em cada país estão em `observacoes` no próprio perfil. Para várias lojas no mesmo
servidor, use uma pasta de dados por país (`LIVRARIA_DADOS=dados/estado_za`).

### Pagamentos por país (PDV e confirmação de pagamentos)

| País | Carteiras e meios eletrónicos |
|---|---|
| Moçambique | M-Pesa (Vodacom), e-Mola (Movitel), mKesh (Tmcel), transferência, cartão/POS, numerário |
| Eswatini | MTN MoMo, e-Mali (Eswatini Mobile), InstaCash, transferência, cartão, numerário |
| África do Sul | cartão/tap, Capitec Pay, PayShap, QR (SnapScan, Zapper, Scan to Pay), EFT/Instant EFT, Apple/Google/Samsung Pay, numerário |
| RD Congo | M-Pesa (Vodacom), Orange Money, Airtel Money, Afrimoney (Africell), transferência, cartão, numerário |
| Ilhas Maurício | MCB Juice, blink by Emtel, my.t money, QR MauCAS, cartão, transferência, numerário |

A lista fica em `pagamentos` no perfil de cada país: ao confirmar um pagamento, a equipa escolhe o meio
usado e o financeiro mostra os totais por meio. Para ligar cobranças automáticas (link de pagamento),
cada operador tem a sua API de comerciante; isso é um passo à parte, país a país.

### Catálogo comum, clientes por país

O catálogo é o mesmo da CPAD em todos os países: cada loja importa o mesmo ficheiro e a importação
acrescenta os produtos novos e atualiza os existentes, sem apagar nada, mantendo o stock local e os preços
ajustados à mão. Fora de Moçambique, os preços vêm de uma tabela local (`--precos tabela.xlsx`) ou são
convertidos de MZN com `conversao_precos.fator` no perfil (ou `--fator`); o stock começa a 0 e é de cada
loja. A base de clientes é própria de cada país (importada só na loja desse país).

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
cadastro, em compras a partir de **5.000 MT em produtos** (sem a taxa de entrega): **30% nos Livros CPAD,
Bíblias CPAD e Harpa Cristã**, **20% nas Lições Bíblicas** e **15% em todo o resto** (outras marcas, CDs, DVDs,
brindes).
Livro/Bíblia CPAD = categoria "CPAD - LIVROS"/"CPAD - BIBLIAS" no ERP, ou livro/Bíblia com ISBN/código de
barras da CPAD (978-85-263, 7908234, 7898203). O sistema calcula sozinho no orçamento e no pedido; quem não está no
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
