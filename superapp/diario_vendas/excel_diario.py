import json,collections as C,datetime,sys
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.utils import get_column_letter
W,S,OUT=sys.argv[1],sys.argv[2],sys.argv[3]
M=json.load(open(W+'/diario_2016_2022.json'));H=json.load(open(S+'/historico.json'))
A20=json.load(open(W+'/an_dez2020.json'));A22=json.load(open(W+'/an_jul2022.json'));D20=json.load(open(W+'/dez2020.json'))
NOME={'1':'Priscila Vilanculos','2':'Sérgio Paulo Fernando (Guacha)','3':'José Tovela','4':'Jorge Bembele','6':'Rodrigues Johane','7':'Damião Sebastião Cau','N/D':'Sem vendedor','':'Sem vendedor'}
def fpg(f):
  f=f.lower()
  if '/' in f: return 'Misto'
  if 'ponto' in f: return 'Cartão (Ponto 24)'
  if 'numer' in f: return 'Dinheiro'
  if 'créd' in f or 'cred' in f: return 'Crédito (fatura)'
  if 'trans' in f or 'trasn' in f: return 'Transferência'
  if 'cheq' in f: return 'Cheque'
  return 'Outro'
liq=lambda x:x['merc']+x['desc']
wb=Workbook();H1=Font(bold=True,color='FFFFFF');FL=PatternFill('solid',fgColor='1F4E79');B=Font(bold=True)
NF='#,##0.00';
def sheet(t,head,rows,widths=None,nf_from=1):
  ws=wb.create_sheet(t[:31]);ws.append(head)
  for c in ws[1]: c.font=H1;c.fill=FL;c.alignment=Alignment(wrap_text=True,vertical='center')
  for r in rows: ws.append(r)
  for row in ws.iter_rows(min_row=2):
    for c in row:
      if isinstance(c.value,float): c.number_format=NF
      elif isinstance(c.value,int) and c.column>nf_from: c.number_format='#,##0'
  for i,w in enumerate(widths or [],1): ws.column_dimensions[get_column_letter(i)].width=w
  ws.freeze_panes='B2';return ws
yrs=sorted({x['data'][:4] for x in M})
# Resumo
ws=wb.active;ws.title='Resumo'
tot=sum(liq(x) for x in M);docs=len(M)
lin=[('Diário de Vendas por Tipo de Documento — Eticadata (ERP19), Secção Sede',),(),
('Período','01/08/2016 a 31/07/2022'),('Fontes','DiarioVendasTpDoc VELHO.pdf (zip) + DiarioVendasTpDoc3.pdf (dez/2020 completo)'),
('Documentos',docs),('Mercadoria (bruto)',round(sum(x['merc'] for x in M),2)),('Descontos',round(sum(x['desc'] for x in M),2)),
('Vendas líquidas sem IVA',round(tot,2)),('Impostos',round(sum(x['imp'] for x in M),2)),('Total documentos (com IVA)',round(sum(x['total'] for x in M),2)),('Valor pago',round(sum(x['pago'] for x in M),2)),
('Ticket médio (líquido)',round(tot/docs,2)),('Dias com venda',len({x['data'] for x in M})),(),
('Validação','O total do ficheiro grande bate ao cêntimo com o Quadro Resumo oficial (Total Doc. 74 309 357,86; Pago 72 152 689,62).'),
('Atenção 1','O Diário grande só tinha 24 documentos em dez/2020; foi substituído pelo ficheiro DiarioVendasTpDoc3 (834 docs, 1 406 673,92).'),
('Atenção 2','O Diário NÃO inclui todas as faturas nem notas de crédito: dez/2020 faltam 16 FACT + 4 N/CRE (205 945,20); 16–31/07/2022 faltam 5 FACT (49 959,20). Ver folha "Faturas fora do Diário".'),
('Atenção 3','A análise anterior (superapp) inclui todas as faturas a crédito, por isso os totais anuais dela são maiores. Ver "Confronto anterior".'),
('Códigos de vendedor','1 Priscila · 2 Sérgio Paulo (Guacha) · 3 José Tovela · 4 Jorge Bembele · 6 Rodrigues Johane · 7 Damião — identificados por coincidência diária com a análise anterior.')]
for l in lin: ws.append(list(l))
ws['A1'].font=Font(bold=True,size=14);ws.column_dimensions['A'].width=30;ws.column_dimensions['B'].width=120
for r in ws.iter_rows(min_row=3):
  for c in r:
    if isinstance(c.value,float): c.number_format=NF
    if c.column==1: c.font=B
# Por ano
ag=C.defaultdict(lambda:[0,0.,0.,0.,0.])
for x in M: a=ag[x['data'][:4]];a[0]+=1;a[1]+=x['merc'];a[2]+=x['desc'];a[3]+=liq(x);a[4]+=x['total']
sheet('Por ano',['Ano','Docs','Mercadoria','Descontos','Líquido s/ IVA','Total c/ IVA','Ticket médio','Desconto %','Obs.'],[[y,a[0],round(a[1],2),round(a[2],2),round(a[3],2),round(a[4],2),round(a[3]/a[0],2),round(-a[2]/a[1]*100,2),'só ago–dez' if y=='2016' else 'só jan–jul' if y=='2022' else ''] for y,a in sorted(ag.items())],[8,8,16,16,16,16,12,11,14])
# Mensal
mm=C.defaultdict(lambda:[0,0.]);
for x in M: a=mm[x['data'][:7]];a[0]+=1;a[1]+=liq(x)
sheet('Mensal',['Mês','Docs','Líquido s/ IVA','Ticket médio'],[[m,a[0],round(a[1],2),round(a[1]/a[0],2)] for m,a in sorted(mm.items())],[10,8,16,12])
# Vendedor x ano
vy=C.defaultdict(C.Counter);vs=C.defaultdict(lambda:[0,0.,0.,0.,0,0.])
for x in M:
  n=NOME[x['vend']];vy[n][x['data'][:4]]+=liq(x);s=vs[n]
  if x['tipo']=='DEVOL': s[4]+=1;s[5]+=liq(x)
  else: s[0]+=1;s[1]+=x['merc'];s[2]+=x['desc'];s[3]+=liq(x)
ordv=sorted(vy,key=lambda k:-sum(vy[k].values()))
sheet('Vendedor x ano',['Vendedor']+yrs+['Total','% do total'],[[n]+[round(vy[n][y],2) for y in yrs]+[round(sum(vy[n].values()),2),round(sum(vy[n].values())/tot*100,2)] for n in ordv],[30]+[14]*(len(yrs)+2))
sheet('Vendedor desempenho',['Vendedor','Vendas (docs)','Mercadoria','Descontos','Líquido','Ticket médio','Desconto %','Devoluções (n)','Devoluções (valor)','1.º mês','Último mês','Meses ativos','Média por mês ativo'],
 [[n,s[0],round(s[1],2),round(s[2],2),round(s[3],2),round(s[3]/s[0],2),round(-s[2]/s[1]*100,2),s[4],round(s[5],2),
   min(x['data'][:7] for x in M if NOME[x['vend']]==n),max(x['data'][:7] for x in M if NOME[x['vend']]==n),
   len({x['data'][:7] for x in M if NOME[x['vend']]==n}),round(s[3]/len({x['data'][:7] for x in M if NOME[x['vend']]==n}),2)] for n,s in sorted(vs.items(),key=lambda z:-z[1][3])],[30,10,15,15,15,11,10,10,14,9,9,9,15])
# Vendedor x mês
mes=sorted(mm);vm=C.defaultdict(C.Counter)
for x in M: vm[x['data'][:7]][NOME[x['vend']]]+=liq(x)
sheet('Vendedor x mês',['Mês']+ordv+['Total'],[[m]+[round(vm[m][n],2) for n in ordv]+[round(sum(vm[m].values()),2)] for m in mes],[10]+[16]*(len(ordv)+1))
# Meio pagamento
fy=C.defaultdict(C.Counter);fc=C.Counter()
for x in M: g=fpg(x['fp']);fy[g][x['data'][:4]]+=liq(x);fc[g]+=1
ordf=sorted(fy,key=lambda k:-sum(fy[k].values()))
rows=[[g,fc[g]]+[round(fy[g][y],2) for y in yrs]+[round(sum(fy[g].values()),2),round(sum(fy[g].values())/tot*100,2)] for g in ordf]
rows.append(['% cartão no ano','']+[round(fy['Cartão (Ponto 24)'][y]/sum(fy[g][y] for g in fy)*100,2) for y in yrs]+['',''])
sheet('Meio de pagamento',['Meio','Docs']+yrs+['Total','%'],rows,[20,8]+[14]*(len(yrs)+2))
vf=C.defaultdict(C.Counter)
for x in M: vf[NOME[x['vend']]][fpg(x['fp'])]+=liq(x)
sheet('Vendedor x meio pag.',['Vendedor']+ordf+['Total','% cartão','% dinheiro'],[[n]+[round(vf[n][g],2) for g in ordf]+[round(sum(vf[n].values()),2),round(vf[n]['Cartão (Ponto 24)']/sum(vf[n].values())*100,2),round(vf[n]['Dinheiro']/sum(vf[n].values())*100,2)] for n in ordv],[30]+[15]*(len(ordf)+3))
# Detalhe meio original
fo=C.defaultdict(lambda:[0,0.])
for x in M: a=fo[x['fp']];a[0]+=1;a[1]+=liq(x)
sheet('Meio pag. (original)',['Descrição no Eticadata','Grupo','Docs','Líquido'],[[k,fpg(k),a[0],round(a[1],2)] for k,a in sorted(fo.items(),key=lambda z:-z[1][1])],[55,18,8,16])
# Tipo documento
ty=C.defaultdict(C.Counter);tc=C.Counter()
for x in M: ty[x['tipo']][x['data'][:4]]+=liq(x);tc[x['tipo']]+=1
NT={'V/DIN':'Venda a dinheiro','TAL':'Talão de venda','FACT':'Fatura (crédito CC)','DEVOL':'Devolução'}
sheet('Tipo de documento',['Tipo','Descrição','Docs']+yrs+['Total'],[[t,NT.get(t,''),tc[t]]+[round(ty[t][y],2) for y in yrs]+[round(sum(ty[t].values()),2)] for t in sorted(ty,key=lambda k:-sum(ty[k].values()))],[8,22,8]+[14]*(len(yrs)+1))
# Dia da semana / sazonalidade
DS=['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo'];wd=C.defaultdict(lambda:[0,0.,set()])
for x in M:
  d=datetime.date.fromisoformat(x['data']);a=wd[d.weekday()];a[0]+=1;a[1]+=liq(x);a[2].add(x['data'])
sheet('Dia da semana',['Dia','Docs','Líquido','Dias','Média por dia'],[[DS[k],a[0],round(a[1],2),len(a[2]),round(a[1]/len(a[2]),2)] for k,a in sorted(wd.items())],[12,8,16,8,14])
MS=['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];mo=C.defaultdict(C.Counter)
for x in M: mo[int(x['data'][5:7])][x['data'][:4]]+=liq(x)
sheet('Sazonalidade',['Mês']+yrs+['Média anos completos (2017–2021)'],[[MS[k-1]]+[round(mo[k][y],2) for y in yrs]+[round(sum(mo[k][y] for y in ['2017','2018','2019','2020','2021'])/5,2)] for k in range(1,13)],[8]+[14]*(len(yrs)+1))
# Top dias e maiores documentos
td=C.defaultdict(lambda:[0,0.])
for x in M: a=td[x['data']];a[0]+=1;a[1]+=liq(x)
sheet('Melhores dias',['Data','Docs','Líquido'],[[d,a[0],round(a[1],2)] for d,a in sorted(td.items(),key=lambda z:-z[1][1])[:50]],[12,8,16])
sheet('Maiores documentos',['Data','Tipo','Número','Vendedor','Meio','Mercadoria','Desconto','Líquido','Total'],[[x['data'],x['tipo'],x['num'],NOME[x['vend']],x['fp'],x['merc'],x['desc'],round(liq(x),2),x['total']] for x in sorted(M,key=lambda x:-liq(x))[:100]],[11,7,13,28,30,14,13,14,14])
dv=[x for x in M if x['tipo']=='DEVOL']
sheet('Devoluções',['Data','Número','Vendedor','Meio','Mercadoria','Desconto','Líquido'],[[x['data'],x['num'],NOME[x['vend']],x['fp'],x['merc'],x['desc'],round(liq(x),2)] for x in sorted(dv,key=lambda x:x['data'])],[11,13,28,30,14,13,14])
# Faturas fora do Diário
dd={x['tipo']+' '+x['num'] for x in D20}|{x['tipo']+' '+x['num'] for x in M}
fora=[x for x in A20+A22 if x['tipo']+' '+x['num'] not in dd]
sheet('Faturas fora do Diário',['Data','Tipo','Número','Qtd','Valor','Desconto','Líquido','Origem'],[[x['data'],x['tipo'],x['num'],x['qtd'],x['valor'],x['desc'],x['liq'],'Análise de Vendas dez/2020' if x['data']<'2021' else 'Análise de Vendas 16–31/07/2022'] for x in sorted(fora,key=lambda x:x['data'])]+[['Total','','',round(sum(x['qtd'] for x in fora),3),'','',round(sum(x['liq'] for x in fora),2),'']],[11,7,13,9,14,13,14,30])
# Análises: unidades
def un(A,lab):
  t=C.defaultdict(lambda:[0,0.,0.])
  for x in A: a=t[x['tipo']];a[0]+=1;a[1]+=x['qtd'];a[2]+=x['liq']
  return [[lab,k,a[0],round(a[1],3),round(a[2],2),round(a[1]/a[0],2) if a[0] else 0,round(a[2]/a[1],2) if a[1] else 0] for k,a in sorted(t.items())]
sheet('Unidades (Análises)',['Período','Tipo','Docs','Unidades','Líquido','Unid./doc','Preço médio/unid.'],un(A20,'Dez/2020')+un(A22,'16–31/07/2022'),[16,8,8,10,14,10,14])
# Confronto com análise anterior
hy=C.Counter();hf=C.Counter()
for r in H['dias']:
  if r[1]=='ERP19' and '2016-08-01'<=r[0]<='2022-07-31': hy[r[0][:4]]+=r[4]
for d,cat,f,v in H['fp']:
  if '2016-08-01'<=d<='2022-07-31' and f=='A crédito (fatura)': hf[d[:4]]+=v
dy=C.Counter();dyf=C.Counter()
for x in M:
  dy[x['data'][:4]]+=liq(x)
  if x['tipo']=='FACT': dyf[x['data'][:4]]+=liq(x)
sheet('Confronto anterior',['Ano','Diário (este)','Faturas no Diário','Análise anterior (ERP19)','Faturas a crédito na análise anterior','Diferença','Diferença sem faturas'],
 [[y,round(dy[y],2),round(dyf[y],2),round(hy[y],2),round(hf[y],2),round(hy[y]-dy[y],2),round((hy[y]-hf[y])-(dy[y]-dyf[y]),2)] for y in yrs],[8,16,16,18,20,16,18])
# Análise anterior: artigos, tipos de entidade, zonas (referência)
sheet('Artigos (anterior)',['Código','Artigo','Unidades','Valor','Docs'],[[a[0],a[1].replace('  Unidade:Un',''),a[2],round(a[3],2),a[4]] for a in H['artigos'][:300]],[10,60,10,16,8])
sheet('Tipos entidade (anterior)',['Sistema','Tipo de entidade','Grupo','Valor','Docs'],[[t[0],t[1],t[2],round(t[3],2),t[4]] for t in H['tipos']],[8,22,18,16,8])
sheet('Zonas (anterior)',['Sistema','Vendedor','Zona','Varejo','Atacado','Igrejas/inst.'],[[z[0],z[1],z[2],round(z[3],2),round(z[4],2),round(z[5],2)] for z in H['zonas']],[8,30,16,14,14,14])
av={};rows=[]
for vn,L in H['artigosVend'].items():
  for a in L[:25]: rows.append([vn,a[0],a[1].replace('  Unidade:Un',''),a[2],round(a[3],2)])
sheet('Top artigos x vendedor (ant.)',['Vendedor','Código','Artigo','Unidades','Valor'],rows,[30,10,55,10,16])
# Documentos
sheet('Documentos',['Data','Tipo','Número','Cód. vend.','Vendedor','Meio (original)','Meio (grupo)','Mercadoria','Descontos','Líquido','Impostos','Total','Pago'],
 [[x['data'],x['tipo'],x['num'],x['vend'],NOME[x['vend']],x['fp'],fpg(x['fp']),x['merc'],x['desc'],round(liq(x),2),x['imp'],x['total'],x['pago']] for x in sorted(M,key=lambda x:(x['data'],x['num']))],[11,7,13,6,28,32,16,13,12,13,10,13,13])
wb.save(OUT);print('ok',OUT,len(wb.sheetnames),'folhas')
