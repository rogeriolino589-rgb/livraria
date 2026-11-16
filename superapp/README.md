# Superapp CPAD Moçambique

Página publicada: o ERP da CPAD (artefacto privado do dono). Este diretório guarda o código dos módulos acrescentados
ao ERP; os dados de vendas e clientes NÃO entram no git.

- `modulos/mapas_eticadata.js` — Vendas › Mapas do Eticadata (Diário de Vendas + Mapa de Caixa, conferência, Financeiro).
- `modulos/historico_e_roger.js` — Vendas › Histórico de vendas (ERP19 + ERP22) e o assistente **Roger**
  (capacidade `sample`: o Claude consulta os dados por funções da página, só leitura).
- `modulos/apps_cpad.js` — grupo «Apps CPAD»: Leads Moçambique e Controlo Financeiro 3D como páginas internas
  (`apps/*.html`), mais links para a Análise do Projeto e o Relatório Estratégico.

Atualizar o histórico: exportar do Eticadata os relatórios da Análise de Vendas para uma pasta e correr

    python -c "from pathlib import Path; from livraria_agentes.interno.relatorio_vendas import exportar_json; print(exportar_json(Path('PASTA'), Path('historico.json')))"

e substituir o conteúdo de `<script id="histData">` na página antes de publicar.
