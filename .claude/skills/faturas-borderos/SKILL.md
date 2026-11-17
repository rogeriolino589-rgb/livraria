---
name: faturas-borderos
description: Reconhece, regista e concilia faturas, recibos, borderôs, comprovativos M-Pesa/e-Mola/mKesh, extractos de fornecedores e relatórios de vendas que chegam ao Outlook da CPAD Moçambique. Use quando pedirem "faturas do mês", "o que devemos ao fornecedor X", "borderôs", "conciliar", "comprovativos" ou "documentos dos e-mails".
---

# Faturas, borderôs e conciliação — CPAD Moçambique

## Onde estão os documentos
- Caixa **rogerio.gomes@cpad.com.br** (Outlook, ferramentas `mcp__Microsoft_365__*`). Recebe em cópia o que chega a
  mocambique@cpad.com.br (a caixa partilhada ainda não dá acesso direto: falta delegação).
- Formatos reconhecidos (nov/2026):
  - **Relatório de vendas diário**: assunto "Vendas CPAD Moçambique", anexo `NN-Faturamento - Filial Moçambique <Mês> <Ano>.xlsx`.
  - **Extracto de fornecedor**: PDF "Conta Corrente CPAD Livraria - Moçambique" (Data, TipoDoc, NumDoc, Débito, Crédito, Saldo).
  - **Borderô**: aviso do banco "Registamos a operação abaixo descriminada" ou PDF `Transferencias_Entre_Contas_Do_Mesmo_Banco (N).pdf`.
    Quem envia os borderôs é o Silvio Tomé (silvio.tome@cpad.com.br).
  - **Faturas de fornecedor**: PDF anexo ("Envio de Faturas e Dados Bancários").
  - **Recibos**: PDF digitalizado (SKM_...): não tem texto, peça à equipa para confirmar o valor.
  - **Comprovativo M-Pesa**: texto "Obrigado por pagar com o M-Pesa" no corpo.

## Passos
1. Procure com `outlook_email_search` (período pedido; sem período, últimos 30 dias). Ignore a publicidade.
2. Classifique com as regras fixas:
   `.venv/bin/python -c "from livraria_agentes.interno.classificar_docs import classificar; print(classificar(ASSUNTO, REMETENTE, [ANEXOS], TEXTO))"`
3. Leia os anexos com `read_resource`. Extractos: `extracto_conta_corrente(texto)` dá saldo final, faturas em aberto e avisos.
4. Registe: data, tipo, emitente, número, valor (`1.234,50 MT`), estado, e-mail de origem.
5. Conciliação por número e valor: **bate**, **diverge**, **sem par**. Fatura paga sem borderô = "falta borderô".

## Regras que nunca se quebram
- Os originais ficam onde estão: não mova, não apague, não marque como lido, não reencaminhe.
- Não envie e-mails nem mensagens e não faça pagamentos.
- Gravar no OneDrive só com autorização, numa pasta nova, sem sobrescrever.
- Diga de onde vem cada número; o que não leu, diga que não leu.

## Qualidade
Casos de teste em `tests/test_classificar_docs.py`. Formato novo: acrescente um caso (dados inventados) antes de
mudar as regras, e corra `.venv/bin/python -m pytest -q tests/test_classificar_docs.py`.
