import json,collections as C,datetime,sys
W,S=sys.argv[1],sys.argv[2]
M=json.load(open(W+'/diario_2016_2022.json'));H=json.load(open(S+'/historico.json'))
A20=json.load(open(W+'/an_dez2020.json'));A22=json.load(open(W+'/an_jul2022.json'));D20=json.load(open(W+'/dez2020.json'))
V=['Sérgio Paulo Fernando (Guacha)','José Tovela','Priscila Vilanculos','Jorge Bembele','Rodrigues Johane','Damião Sebastião Cau','Sem vendedor (N/D)']
COD={'2':0,'3':1,'1':2,'4':3,'6':4,'7':5,'N/D':6,'':6}
FPG=['Cartão (Ponto 24)','Dinheiro','Misto','Crédito (fatura)','Transferência','Cheque','Outro']
def fpg(f):
  f=f.lower()
  if '/' in f: return 2
  if 'ponto' in f: return 0
  if 'numer' in f: return 1
  if 'créd' in f or 'cred' in f: return 3
  if 'trans' in f or 'trasn' in f: return 4
  if 'cheq' in f: return 5
  return 6
liq=lambda x:x['merc']+x['desc']
m={};f={};t={};wd=[[0,0,set()] for _ in range(7)];vp=[[0,0.,0.,0.,0,0.] for _ in V]
for x in M:
  k=x['data'][:7];i=COD[x['vend']]
  a=m.setdefault(k,[[0]*len(V),[0]*len(V),0.,0.])  # liq por vend, docs por vend, mercadoria, desconto
  a[0][i]+=liq(x);a[1][i]+=1;a[2]+=x['merc'];a[3]+=x['desc']
  b=f.setdefault(k,[0]*len(FPG));b[fpg(x['fp'])]+=liq(x)
  c=t.setdefault(x['data'][:4],{});c[x['tipo']]=c.get(x['tipo'],0)+liq(x)
  d=datetime.date.fromisoformat(x['data']).weekday();wd[d][0]+=1;wd[d][1]+=liq(x);wd[d][2].add(x['data'])
  p=vp[i]
  if x['tipo']=='DEVOL': p[4]+=1;p[5]+=liq(x)
  else: p[0]+=1;p[1]+=x['merc'];p[2]+=x['desc'];p[3]+=liq(x)
r2=lambda v:round(v,2)
m={k:[[r2(z) for z in a[0]],a[1],r2(a[2]),r2(a[3])] for k,a in sorted(m.items())}
f={k:[r2(z) for z in b] for k,b in sorted(f.items())}
t={y:{k:r2(v) for k,v in c.items()} for y,c in sorted(t.items())}
h=C.Counter();hd=C.Counter();hy=C.Counter();hf=C.Counter()
for r in H['dias']:
  if r[1]=='ERP19' and '2016-08-01'<=r[0]<='2022-07-31': h[r[2]]+=r[4];hd[r[2]]+=r[3];hy[r[0][:4]]+=r[4]
for d,cat,fo,v in H['fp']:
  if '2016-08-01'<=d<='2022-07-31' and fo=='A crédito (fatura)': hf[d[:4]]+=v
dd={x['tipo']+' '+x['num'] for x in D20}|{x['tipo']+' '+x['num'] for x in M}
fora=[[x['data'],x['tipo'],x['num'],x['qtd'],x['liq']] for x in sorted(A20+A22,key=lambda x:x['data']) if x['tipo']+' '+x['num'] not in dd]
td=C.Counter()
for x in M: td[x['data']]+=liq(x)
big=[[x['data'],x['tipo'],x['num'],COD[x['vend']],r2(liq(x))] for x in sorted(M,key=lambda x:-liq(x))[:20]]
import os
AL=json.load(open(W+'/alvo_ref.json')) if os.path.exists(W+'/alvo_ref.json') else {}
hyall=C.Counter()
for r in H['dias']: hyall[r[0][:4]]+=r[4]
out=dict(alvo=AL,hy={k:r2(v) for k,v in sorted(hyall.items())},V=V,FPG=FPG,m=m,f=f,t=t,wd=[[a[0],r2(a[1]),len(a[2])] for a in wd[:6]],vp=[[p[0],r2(p[1]),r2(p[2]),r2(p[3]),p[4],r2(p[5])] for p in vp],
 hist=dict(v=[[r2(h[n]),hd[n]] for n in V],y={y:[r2(hy[y]),r2(hf[y])] for y in sorted(hy)}),fora=fora,top=[[d,r2(v)] for d,v in td.most_common(15)],big=big,
 tot=dict(docs=len(M),merc=r2(sum(x['merc'] for x in M)),desc=r2(sum(x['desc'] for x in M)),liq=r2(sum(liq(x) for x in M)),total=r2(sum(x['total'] for x in M)),pago=r2(sum(x['pago'] for x in M))))
json.dump(out,open(W+'/dv_dados.json','w'),ensure_ascii=False,separators=(',',':'));print(len(json.dumps(out)))
