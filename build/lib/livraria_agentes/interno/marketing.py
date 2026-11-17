"""Métodos de marketing do assistente interno, adaptados à livraria.

Cada método é um roteiro de trabalho que o assistente segue quando a equipe pede
(estratégia, calendário de 30 dias, ganchos, roteiro de Reels...). As regras
comuns valem para todos: nada de dados, depoimentos, escassez ou resultados
inventados, e o tom é o da livraria.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

REGRAS = """\
Regras para qualquer conteúdo da livraria:
- Use só dados reais: preços e stock do catálogo, vendas dos ERPs, números que a equipe colar. Se faltar um dado,
  diga qual é e como obtê-lo; nunca invente tendências, depoimentos, resultados, escassez ou descontos.
- Tom da casa: respeitoso, acolhedor e cristão quando o assunto pedir, sem manipulação nem pressão de venda.
  Versículos sempre com a referência correta.
- Pedidos de oração e assuntos pastorais nunca viram oferta de venda.
- Separe o que é evidência, interpretação e hipótese.
- Adapte o formato à rede: Instagram (Reels, carrossel, stories), Facebook (posts e grupos), TikTok (vídeo curto
  vertical, gancho nos 2 primeiros segundos), Threads (texto curto de conversa).
- Tudo sai como rascunho para a equipe aprovar."""

METODOS = {
    "estrategia": ("Estratégia de marketing (planeamento reverso)", """\
Comece pela meta e trabalhe de trás para a frente:
1. Quantas vendas são precisas para a meta (use o ticket médio real dos ERPs).
2. Etapas que acontecem antes de cada venda (descoberta, contacto, visita à loja ou WhatsApp, pagamento).
3. Gargalos atuais em aquisição, oferta, conversão e retenção.
4. Compare cinco iniciativas por impacto, custo, tempo e facilidade de execução.
5. Escolha as três com melhor relação esforço/benefício.
Entregue um plano de 30 dias com prioridades semanais, tarefas, responsáveis sugeridos e indicadores, e termine com
três ações para fazer já. Nada de plano genérico: se faltarem dados, liste as hipóteses e como validá-las."""),
    "publico_concorrentes": ("Pesquisa de público e concorrentes", """\
Investigação em três camadas, usando a pesquisa na web quando possível (cite fontes e datas):
1. Demanda: problemas, desejos, dúvidas e objeções de quem procura Bíblias, livros cristãos e material de Escola
   Dominical no país da loja; situações que aceleram a compra (datas, eventos de igreja, ofertas para presente).
2. Concorrência: oferta, preço, promessa, diferenciação, conteúdo e argumentos de outras livrarias e editoras.
3. Oportunidades: necessidades pouco atendidas e posicionamentos possíveis.
Entregue cinco problemas prioritários do público, uma comparação dos concorrentes, cinco oportunidades de
posicionamento e dez mensagens de marketing baseadas nas descobertas."""),
    "oferta": ("Oferta de venda (construir, confrontar, revisar)", """\
1. Construção: benefício central, por que o produto é útil, três propostas de valor, título, subtítulo e cinco
   argumentos, apresentação comercial clara.
2. Confronto: assuma o papel de um comprador desconfiado e questione preço, necessidade, diferença, risco e
   credibilidade.
3. Revisão: reescreva respondendo às objeções só com informações verdadeiras.
Entregue a oferta final, um texto curto para anúncio e a estrutura de uma página ou mensagem de venda."""),
    "calendario_30_dias": ("Calendário de 30 dias de conteúdo", """\
Distribua os conteúdos em quatro funções: descoberta (atrair pessoas novas), educação (ensinar algo útil),
autoridade (mostrar conhecimento e credibilidade) e conversão (ligar uma necessidade a um produto).
Crie 30 pautas sem repetir o mesmo ângulo, para as redes pedidas. Para cada uma: data, rede, formato, função,
título com promessa específica, problema abordado, estrutura, gancho, texto, CTA e produto relacionado.
Depois desenvolva os primeiros sete conteúdos completos (capa, roteiro, texto e CTA) e salve o calendário com
conteudo_calendario_salvar. Ideias para a casa: segunda "comece a semana com a Palavra", quarta "livro da
semana", sexta "presente que edifica", domingo versículo e lição de Escola Dominical."""),
    "campanha_anuncios": ("Campanha e anúncios (laboratório de criativos)", """\
Teste quatro hipóteses de mensagem: A) problema do comprador, B) benefício, C) demonstração do produto,
D) diferença em relação às alternativas. Para cada uma: vídeo curto, anúncio estático e variação de texto,
com gancho, roteiro, texto na tela, ideia visual, CTA e argumento principal. Escolha os quatro melhores e monte um
plano de teste com orçamento, variável principal, métricas e critério de decisão. Não prometa resultados,
respeite as políticas de anúncios da Meta e do TikTok e diga o que precisa ser verificado antes de publicar."""),
    "funil": ("Funil de vendas por estados", """\
Desenhe a jornada: 1) descoberta, 2) interesse (que material gratuito ou conteúdo justifica o contacto — por
exemplo um plano de leitura bíblica ou uma lição de amostra), 3) captura (como a pessoa pede e recebe, com
consentimento), 4) confiança, 5) oferta (sem interromper a experiência), 6) conversão (WhatsApp, pagamento móvel ou loja).
Para cada estado: gatilho, mensagem, ação da pessoa, próxima etapa e indicador. Escreva os textos do conteúdo
inicial, CTA, mensagens automáticas, entrega do material e apresentação da oferta. Por fim, percorra o funil como
um cliente, aponte cinco pontos de abandono e corrija os mais importantes."""),
    "analise_resultados": ("Análise e melhoria do marketing (diagnóstico por gargalos)", """\
1. Leitura: organize as métricas disponíveis (alcance, visitas, cliques, contactos, vendas, receita, investimento);
   use também as vendas reais dos ERPs.
2. Localização: onde está a maior perda entre atenção e venda.
3. Hipóteses: três explicações por gargalo (conteúdo, público, oferta, página/canal, funil, medição).
4. Priorização por impacto, custo, esforço e confiança.
5. Experimentação: cinco testes com hipótese, mudança, métrica principal e critério.
Entregue diagnóstico, três gargalos prioritários, o que manter/corrigir/parar, plano dos próximos sete dias e um
modelo de relatório. Não atribua causa sem evidência."""),
    "auditoria_instagram": ("Auditoria do Instagram", """\
Com os cinco conteúdos de melhor desempenho que a equipe colar (ou os dados da conta, se ligada), aponte o que está
a dar certo, o que trava o crescimento e que formatos e temas intensificar."""),
    "ideias_conteudo": ("Ideias de conteúdo", """\
Cinco ideias curtas e específicas com potencial de partilha. Se usar tendências, pesquise na web e cite; se não
houver dados atuais, diga."""),
    "ganchos": ("Ganchos (dores em ganchos)", """\
Liste dez dúvidas ou dores reais do público sobre o tema e transforme cada uma num gancho de até 10 palavras,
usando curiosidade, contraste ou surpresa, sem clichês nem sensacionalismo."""),
    "roteiro_reels": ("Roteiro de Reels / TikTok", """\
Roteiro de 30 segundos com gancho, desenvolvimento e CTA para comentar ou guardar. Frases simples, texto na tela e
sugestão de imagem para cada cena."""),
    "prova_social": ("Prova social", """\
Com um resultado comprovado que a equipe fornecer (avaliação real de cliente, número de vendas dos ERPs), crie cinco
frases curtas de prova social. Sem resultado real, não faça: peça o dado."""),
    "carrossel": ("Conteúdo para guardar (carrossel)", """\
Cinco dicas práticas sobre o tema, até 12 palavras cada, organizadas num carrossel claro: capa, 5 slides e slide
final com CTA."""),
    "reaproveitar": ("Reaproveitar conteúdo", """\
Transforme o texto dado num roteiro de Reel de 7 segundos, num carrossel de 5 slides e num post estático, adaptando
formato e linguagem a cada rede."""),
    "ctas": ("CTAs", """\
Dez CTAs curtos e criativos para incentivar comentários ou que guardem o post, sem frases genéricas. Se o CTA pedir
para comentar uma palavra (ex.: QUERO), diga o que a pessoa vai receber em privado."""),
}


def metodo(nome: str) -> dict:
    titulo, texto = METODOS[nome]
    return {"metodo": nome, "titulo": titulo, "instrucoes": texto, "regras": REGRAS}


def salvar_calendario(pasta: Path, titulo: str, itens: list[dict]) -> dict:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    colunas = ["data", "rede", "formato", "funcao", "tema", "gancho", "texto", "cta", "produto"]
    livro = Workbook()
    aba = livro.active
    aba.title = "Calendário"
    aba.append([c.capitalize() for c in colunas])
    for celula in aba[1]:
        celula.font = Font(bold=True)
    for item in sorted(itens, key=lambda i: i.get("data") or ""):
        aba.append([item.get(c) for c in colunas])
    larguras = {"A": 12, "B": 12, "C": 14, "D": 14, "E": 30, "F": 35, "G": 70, "H": 30, "I": 25}
    for coluna, largura in larguras.items():
        aba.column_dimensions[coluna].width = largura
    for linha in aba.iter_rows(min_row=2):
        for celula in linha:
            celula.alignment = Alignment(wrap_text=True, vertical="top")
    Path(pasta).mkdir(parents=True, exist_ok=True)
    nome = "".join(c if c.isalnum() else "_" for c in titulo)[:40] or "calendario"
    arquivo = Path(pasta) / f"{nome}_{datetime.now():%Y%m%d%H%M%S}.xlsx"
    livro.save(arquivo)
    return {"ok": True, "arquivo": str(arquivo), "conteudos": len(itens)}
