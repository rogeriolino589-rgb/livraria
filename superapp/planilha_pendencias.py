import json,sys,collections as C
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter
B,S,OUT=sys.argv[1],sys.argv[2],sys.argv[3]
A=json.load(open(B+'ajustes_fin.json'));excl=set(A['remover'])
R=[x for x in json.load(open(B+'removidos_sem_documento.json')) if x['id'] not in excl and not (x['id'].startswith('est-scan-') and x['id']>='est-scan-2022-07')]
F=[x for x in json.load(open(S+'/estimativas.json')) if x['id'].startswith('fol-')]+[x for x in A['acrescentar'] if x['id'].startswith('scanfat-')]
ONDE={'Renda da loja':'Borderô BCI (transferência ao senhorio) · recibo de renda do senhorio · Outlook "renda"','Renda da gerência (casa)':'Borderô BCI · recibo de renda · contrato de arrendamento','Serviços contabilísticos':'Fatura Scanaudit do mês (e-mail "SALÁRIOS DE <MÊS> + INSS + FACTURA") · borderô de pagamento',
 'Salários':'Borderô BCI dos salários (o recibo Scanaudit já existe)','INSS':'Guia INSS paga / borderô (a guia Scanaudit já existe)','Outros impostos':'Guias da AT (IRPS, IVA, etc.) e respetivo borderô','Permissão de comércio varejista':'Licença / guia do Município e comprovativo','Gráfica':'Fatura da gráfica e comprovativo de pagamento','IRPC':'Guia M/IRPC da AT e borderô','Compras de mercadoria (CPAD Brasil)':'Invoice CPAD Brasil e SWIFT','Compra de passagens':'Fatura da agência / bilhete e comprovativo','IVA':'Guia de IVA e borderô'}
wb=Workbook();ws=wb.active;ws.title='Pendências'
H=['Nº','Mês','Data ref.','Categoria','Beneficiário esperado','Valor (MT)','Origem do valor','O que falta','Onde procurar','Estado','Documento encontrado / justificação','Responsável','Observações','ID interno']
ws.append(H)
rows=[]
for x in R:
  orig='Estimativa (sem documento)' if x['id'].startswith('est-') else 'Total mensal do app Oreate (sem documento)'
  rows.append([x['data'][:7],x['data'],x['cat'],x.get('parte') if not str(x.get('parte','')).startswith('(') else '',round(x['valor'],2),orig,'Fatura/recibo e borderô',ONDE.get(x['cat'],'Fatura e borderô'),'Por procurar','','','',x['id']])
for x in F:
  rows.append([x['data'][:7],x['data'],x['cat'],'Trabalhadores (via Scanaudit)' if x['cat']=='Salários' else 'INSS' if x['cat']=='INSS' else x['parte'],round(x['valor'],2),'Fatura Scanaudit no Outlook (documento existe)' if x['id'].startswith('scanfat-') else 'Recibos/guia Scanaudit (documento existe)','Só o borderô do pagamento',ONDE.get(x['cat'],''),'Por procurar','','','Já conta nas despesas (tem recibo/guia)',x['id']])
rows.sort(key=lambda r:(r[0],r[2]))
for i,r in enumerate(rows,1): ws.append([i]+r)
hf=Font(bold=True,color='FFFFFF');fill=PatternFill('solid',fgColor='1F4E79')
for c in ws[1]: c.font=hf;c.fill=fill;c.alignment=Alignment(wrap_text=True,vertical='center')
W=[5,9,11,26,28,14,30,24,48,14,40,14,30,34]
for i,w in enumerate(W,1): ws.column_dimensions[get_column_letter(i)].width=w
for r in ws.iter_rows(min_row=2):
  r[5].number_format='#,##0.00'
  if 'documento existe' in str(r[6].value): 
    for c in r: c.fill=PatternFill('solid',fgColor='EEF5EA')
dv=DataValidation(type='list',formula1='"Por procurar,Em busca,Encontrado,Justificado,Não procede"',allow_blank=True);ws.add_data_validation(dv);dv.add(f'J2:J{len(rows)+1}')
ws.freeze_panes='B2';ws.auto_filter.ref=f'A1:N{len(rows)+1}'
# Resumo
r2=wb.create_sheet('Resumo')
r2.append(['Pendências de borderô e documentos — despesas administrativas (desde jun/2022)']);r2['A1'].font=Font(bold=True,size=13)
r2.append(['Regra: só entram nas despesas administrativas os lançamentos com documento (borderô, recibo/guia ou fatura). Os sem documento ficam aqui para busca ou justificação.'])
r2.append([])
r2.append(['Categoria','Sem documento (fora das despesas)','Valor','Com recibo, falta borderô','Valor','Total a procurar'])
agg=C.defaultdict(lambda:[0,0.,0,0.])
for r in rows:
  a=agg[r[2]]
  if 'documento existe' in r[5]: a[2]+=1;a[3]+=r[4]
  else: a[0]+=1;a[1]+=r[4]
for k,a in sorted(agg.items(),key=lambda z:-(z[1][1]+z[1][3])): r2.append([k,a[0],round(a[1],2),a[2],round(a[3],2),round(a[1]+a[3],2)])
t=[sum(a[i] for a in agg.values()) for i in range(4)];r2.append(['TOTAL',t[0],round(t[1],2),t[2],round(t[3],2),round(t[1]+t[3],2)])
for c in r2[4]: c.font=hf;c.fill=fill
for row in r2.iter_rows(min_row=5):
  for c in row[2::1]:
    if isinstance(c.value,float): c.number_format='#,##0.00'
r2[r2.max_row][0].font=Font(bold=True)
for i,w in enumerate([36,26,16,24,16,18],1): r2.column_dimensions[get_column_letter(i)].width=w
# por ano
r3=wb.create_sheet('Por ano')
r3.append(['Ano','Itens','Valor sem documento','Itens só sem borderô','Valor só sem borderô'])
ya=C.defaultdict(lambda:[0,0.,0,0.])
for r in rows:
  a=ya[r[0][:4]]
  if 'documento existe' in r[5]: a[2]+=1;a[3]+=r[4]
  else: a[0]+=1;a[1]+=r[4]
for y,a in sorted(ya.items()): r3.append([y,a[0],round(a[1],2),a[2],round(a[3],2)])
for c in r3[1]: c.font=hf;c.fill=fill
for i,w in enumerate([8,8,20,20,20],1): r3.column_dimensions[get_column_letter(i)].width=w
wb.move_sheet('Resumo',offset=-1)
wb.save(OUT);print(len(rows),'linhas;',t)
