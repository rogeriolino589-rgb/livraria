import csv,json,statistics as st,calendar,sys
from collections import defaultdict
B='/home/user/livraria/relatorios/saidas_admin/'
rows=[r for r in csv.reader(open(B+'borderos.tsv',encoding='utf-8'),delimiter='\t') if r]
def kind(b,d):
    t=(b+' '+d).upper()
    if 'VISTO' in t or 'ACORDO EX' in t or 'FERIAS' in t: return None
    if 'SALARIO' in t or 'SALÁRIO' in t: return 'sal'
    if 'INSS' in t: return 'inss'
    if 'SCANAUDIT' in t: return 'scan'
    if 'NARGISBANU' in t or 'ALUGUEL LOJA' in t or 'RENDA DA LOJA' in t: return 'loja'
    if 'PAULA ALEXANDRA' in t or 'GANI' in t: return 'casa'
    return None
M=defaultdict(float); have=defaultdict(set)
for r in rows:
    k=kind(r[2],r[4])
    if k: M[(k,r[0][:7])]+=float(r[3]); have[k].add(r[0][:7])
FULL={m for m in have['sal'] if M[('sal',m)]>=150000}
ms=[f'{y}-{m:02d}' for y in range(2022,2027) for m in range(1,13) if '2022-06'<=f'{y}-{m:02d}'<='2026-10']
def med(k,y):
    for yy in [y,str(int(y)-1),str(int(y)+1),str(int(y)-2)]:
        v=[M[(k,m)] for m in (FULL if k=='sal' else have[k]) if m[:4]==yy]
        if v: return round(st.median(v),2)
    return round(st.median([M[(k,m)] for m in (FULL if k=='sal' else have[k])]),2)
CAT={'sal':'Salários','inss':'INSS','scan':'Serviços contabilísticos','loja':'Renda da loja','casa':'Renda da gerência (casa)'}
out=[]
for k in CAT:
    for m in ms:
        part=0
        if m in have[k]:
            if k=='sal' and m not in FULL: part=M[('sal',m)]
            else: continue
        if k=='casa' and m in ('2023-03','2023-04'): continue   # cobertos pela entrada do apartamento (270 000)
        if k=='loja': v=105000.0 if m<'2022-10' else 120000.0
        elif k=='casa': v=55900.0 if m<'2023-03' else 90000.0
        elif k=='scan': v=31320.0
        else: v=round(med(k,m[:4])-part,2)
        if v<=0: continue
        y,mm=map(int,m.split('-'))
        out.append({'id':f'est-{k}-{m}','data':f'{m}-{calendar.monthrange(y,mm)[1]:02d}','tipo':'S','cat':CAT[k],'parte':'ESTIMATIVA — sem comprovativo','fp':'Transferência bancária','valor':v,'nota':('ESTIMATIVA (diferença para a folha normal do mês; já há '+str(part)+' em borderôs) ' if part else 'ESTIMATIVA (valor fixo conhecido) ')+'— não há borderô deste mês; apagar/substituir quando aparecer o comprovativo','est':True})
json.dump(out,open(sys.argv[1],'w'),ensure_ascii=False)
tot=defaultdict(float)
for x in out: tot[(x['cat'],x['data'][:4])]+=x['valor']
for c in CAT.values(): print(c,{y:round(tot[(c,y)]) for y in ['2022','2023','2024','2025','2026']},sum(1 for x in out if x['cat']==c),'meses')
print('total',round(sum(x['valor'] for x in out)),len(out))
