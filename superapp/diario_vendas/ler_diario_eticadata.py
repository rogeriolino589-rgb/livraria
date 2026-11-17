import re,json,sys
def n(s): return float(s.replace(' ','').replace(',','.'))
NUMS=re.compile(r'(-?\d{1,3}(?: \d{3})*,\d\d)\s+(-?\d{1,3}(?: \d{3})*,\d\d)\s+(-?\d{1,3}(?: \d{3})*,\d\d)\s+(-?\d{1,3}(?: \d{3})*,\d\d)\s+(-?\d{1,3}(?: \d{3})*,\d\d)\s+(-?\d{1,3}(?: \d{3})*,\d\d)\s+(-?\d{1,3}(?: \d{3})*,\d\d)\s*$')
HEAD=re.compile(r'^\s*(\d\d)/(\d\d)/(\d{4})\s+(\S+)\s+(\d{4}-\d+)\s+(\d+)?\s*(.*)$')
lines=open(sys.argv[1],encoding='utf-8').read().split('\n')
out=[];bad=[];i=0
while i<len(lines):
  h=HEAD.match(lines[i])
  if not h: i+=1;continue
  buf=lines[i];j=i;m=NUMS.search(buf)
  while not m and j<i+4 and j+1<len(lines) and not HEAD.match(lines[j+1]):
    j+=1;
    if lines[j].strip(): buf+=' '+lines[j].strip()
    m=NUMS.search(buf)
  if not m:
    N1=re.compile(r'-?\d{1,3}(?: \d{3})*,\d\d(?!\d)')
    hm=HEAD.match(buf);rest=buf[hm.start(7):];ns=N1.findall(rest)
    if len(ns)>=7:
      dd,mm,yy,t,num,v,_=hm.groups();g=[n(x) for x in ns[-7:]]
      fp=re.sub(r'\s+',' ',N1.sub(' ',rest)).strip()
      out.append(dict(data=f'{yy}-{mm}-{dd}',tipo=t,num=num,vend=v or '',fp=fp,merc=g[0],desc=g[1],imp=g[2],total=g[4],pago=g[5]))
    else: bad.append(buf)
    i=j+1;continue
  dd,mm,yy,t,num,v,rest=HEAD.match(buf).groups()
  fp=re.sub(r'\s+',' ',buf[HEAD.match(buf).start(7):m.start()]).strip()
  g=[n(x) for x in m.groups()]
  out.append(dict(data=f'{yy}-{mm}-{dd}',tipo=t,num=num,vend=v or '',fp=fp,merc=g[0],desc=g[1],imp=g[2],total=g[4],pago=g[5]))
  i=j+1
json.dump(out,open(sys.argv[2],'w'))
print(len(out),'linhas; falhas',len(bad));[print(repr(b[:200])) for b in bad[:6]]
print('total doc',round(sum(x['total'] for x in out),2),'pago',round(sum(x['pago'] for x in out),2))
