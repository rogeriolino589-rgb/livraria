import csv,json,re,sys,calendar
from collections import Counter
B='/home/user/livraria/relatorios/saidas_admin/'
def cat(b,d):
    t=(b+' '+d).upper()
    if 'PRE-PAGO' in t or 'CARREGAMENTO' in t: return None
    if 'VISTO' in t: return 'Vistos de trabalho / imigração'
    if 'ACORDO EX-FUNC' in t: return 'Indemnização / acordo com ex-funcionário'
    if 'SALARIO' in t or 'SALÁRIO' in t: return 'Salários'
    if 'INSS' in t: return 'INSS'
    if 'IRPC' in t: return 'IRPC'
    if 'IRPS' in t: return 'IRPS'
    if 'AUTORIDADE TRIB' in t or 'IMPOSTO' in t or 'FINANCAS' in t: return 'Pagamento de impostos'
    if 'CMM' in t or 'MUNICIPAL' in t: return 'CMM — receitas municipais'
    if 'NARGISBANU' in t or 'ALUGUEL LOJA' in t or 'RENDA DA LOJA' in t or 'M-PESA' in t: return 'Renda da loja'
    if 'PAULA ALEXANDRA' in t or 'GANI' in t or 'MORADIA' in t or 'RESIDENCIA' in t: return 'Renda da gerência (casa)'
    if 'SCANAUDIT' in t: return 'Serviços contabilísticos'
    if 'MORE-IT' in t or 'MORE IT' in t: return 'Serviços de informática'
    if 'CURSORS' in t: return 'Marketing e publicidade'
    if 'ADVOGAD' in t or 'ADV LDA' in t or 'HONOR' in t: return 'Advogados / serviços jurídicos'
    if 'MARCENARIA' in t or 'CARMO AMERICO' in t: return 'Reforma e instalações'
    if 'JULIA' in t or 'JCAS' in t: return 'Serviços aduaneiros'
    if 'TRANSTREVO' in t: return 'Frete e desembaraço'
    if 'ESCOLAR' in t or 'LIVROS E ETC' in t: return 'Editora escolar / Livros e Etc'
    if 'GLOBAL ALLIANCE' in t: return 'Seguro automóveis'
    if 'MOZSEC' in t or 'MOZ SECURITY' in t: return 'Segurança'
    if 'THIAGO' in t or 'CARRO' in t: return 'Compra de viatura (parcelas)'
    return 'Outros pagamentos (a classificar)'
out=[]
for r in csv.reader(open(B+'borderos.tsv',encoding='utf-8'),delimiter='\t'):
    if not r or not r[0][:4] in ('2022','2023','2024','2025','2026'): continue
    d,op,ben,val,desc,orig=(r+['']*6)[:6]; c=cat(ben,desc); v=float(val)
    if c is None: continue
    if d[:4] in ('2025','2026') and c=='IRPC': continue   # IRPC 2025–26 vem do Oreate
    x={'id':'brd-'+re.sub(r'[^A-Za-z0-9-]','',op),'data':d,'tipo':'S','cat':c,'parte':ben.title()[:60],'fp':'Transferência bancária','valor':round(v,2),'nota':(desc+' · borderô: '+orig)[:220]}
    if v<0: x.update(tipo='E',cat='Outras receitas',valor=round(-v,2),nota='Devolução recebida · '+x['nota'])
    out.append(x)
SW=json.load(open(B+'swifts.json'))
for r in SW:
    if r.get('devolvido'): continue
    b=r['benef'].upper(); g=r.get('grupo') or ''
    if 'CPAD' in b or 'CASA PUB' in b: c='Pagamento ao estrangeiro (CPAD Brasil)'
    elif 'CARGO' in b or 'TRANSIT' in b: c='Transporte de carga'
    elif g=='Compra de viatura': c='Compra de viatura (parcelas)'
    elif 'MONICA' in b or 'AC CONTAB' in b: c='Pagamento ao estrangeiro (outros)'
    else: c='Pagamento ao estrangeiro (outras editoras)'
    nota='SWIFT '+r['ref']+' · '+str(r['valor_moeda'])+' '+r['moeda']+((' · '+r['det']) if r.get('det') else '')
    if c=='Pagamento ao estrangeiro (outros)': nota+=' · saída confirmada pelo gerente'
    out.append({'id':'swf-'+r['ref'],'data':r['data'],'tipo':'S','cat':c,'parte':r['benef'].title()[:60],'fp':'Transferência bancária','valor':round(r['mzn'],2),'nota':nota[:220]})
    if r.get('encargos'): out.append({'id':'swf-'+r['ref']+'-com','data':r['data'],'tipo':'S','cat':'Comissões bancárias','parte':'BCI','fp':'Transferência bancária','valor':round(r['encargos'],2),'nota':'Encargos da ordem de pagamento '+r['ref']})
# Oreate 2025–2026: só as rubricas que os borderôs não cobrem
o=json.load(open(B+'oreate_dados.json'));R=o['SAI_RUB'];D=o['SAI_DATA_M']
TAKE={'Permissão de comércio varejista':'Permissão de comércio varejista','Gráfica':'Gráfica','Compra de passagens':'Compra de passagens','IRPC (incl. imposto por conta 2023)':'IRPC','Outros impostos':'Outros impostos','IVA':'IVA','Importação de livros — Casa Publicadora':'Compras de mercadoria (CPAD Brasil)'}
i=0
for r in R:
    if r.get('g'): continue
    n=r['n']
    if n in TAKE:
        for y in ('2025','2026'):
            for m,v in enumerate(D[y][i],1):
                if v>0: out.append({'id':f"ore-sai-{y}-{m:02d}-"+re.sub(r'[^a-z]','',n.lower())[:18],'data':f"{y}-{m:02d}-{calendar.monthrange(int(y),m)[1]:02d}",'tipo':'S','cat':TAKE[n],'parte':'(total do mês — app Oreate)','fp':'Transferência bancária','valor':round(v,2),'nota':'Oreate · '+n+' · total mensal'})
    i+=1
assert len({x['id'] for x in out})==len(out)
json.dump(out,open(sys.argv[1],'w'),ensure_ascii=False)
c=Counter(x['id'][:7] for x in out); print(len(out),dict(c))
for y in ('2025','2026'): print(y,'borderôs',round(sum(x['valor'] for x in out if x['id'].startswith('brd') and x['data'][:4]==y and x['tipo']=='S')),'oreate',round(sum(x['valor'] for x in out if x['id'].startswith('ore-sai') and x['data'][:4]==y)))
