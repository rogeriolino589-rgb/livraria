import re,json,sys
def n(s): return float(s.replace(' ','').replace(',','.'))
R=re.compile(r'^(\S+)\s+(\d{4}-\d+)\s+(\d\d)/(\d\d)/(\d{4})\s+(-?[\d ]*\d,\d{3})\s+(-?[\d ]*\d,\d\d)\s+(-?[\d ]*\d,\d\d)\s+(-?[\d ]*\d,\d\d)\s*$')
o=[]
for l in open(sys.argv[1],encoding='utf-8'):
  m=R.match(l.strip())
  if m:
    t,num,dd,mm,yy,q,v,d,lq=m.groups();o.append(dict(tipo=t,num=num,data=f'{yy}-{mm}-{dd}',qtd=n(q),valor=n(v),desc=n(d),liq=n(lq)))
json.dump(o,open(sys.argv[2],'w'));print(sys.argv[1][:20],len(o),round(sum(x['liq'] for x in o),2),round(sum(x['qtd'] for x in o),3))
