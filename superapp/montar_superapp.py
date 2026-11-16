import sys,os
S=sys.argv[1]
s=open(S+'/erp/cpad-erp.html',encoding='utf-8').read()
def troca(a,b):
    global s;assert s.count(a)==1,(a[:70],s.count(a));s=s.replace(a,b)
lines=s.split('\n');k=next(n for n,l in enumerate(lines) if l.startswith('<script id="seed8"'))
assert lines[k-2].strip()=='})();' and lines[k-1].strip()=='</script>'
mod=open(S+'/modulo_historico_jarvis.js',encoding='utf-8').read().rstrip('\n')
hist=open(S+'/historico.json',encoding='utf-8').read().replace('</','<\\/')
nav=open(S+'/apps_nav.js',encoding='utf-8').read().rstrip('\n')
lines.insert(k-2,mod)
lines.insert(k+1,'<script id="histData" type="application/json">'+hist+'</script>\n<script>\n'+nav+'\n</script>')
s='\n'.join(lines)
troca("['📥','Mapas do Eticadata','liv','me'],","['📥','Mapas do Eticadata','liv','me'],['📊','Histórico de vendas (Eticadata)','liv','hv'],")
troca(" ['Sistema',["," ['Apps CPAD',[['🎯','Leads Moçambique','app','leads'],['💠','Controlo Financeiro 3D','app','fin3d'],['📄','Análise do Projeto','link','https://claude.ai/artifact/3mh3qxsatyr8UwJwFJqRgu'],['📽','Relatório Estratégico 2026–2034','link','https://claude.ai/artifact/AWtdoWYnn2VQt5Qd7XX8gg']]],\n ['Sistema',[")
troca("async function go(mod,sub){","async function go(mod,sub){if(mod==='link'){window.open(sub,'_blank','noopener');return}if(mod==='app'){window.abrirAppCPAD(sub);return}{const w=document.getElementById('appW');if(w)w.hidden=true;B.classList.remove('app-on')}")
troca("<title>CPAD ERP Moçambique — Livraria</title>","<title>CPAD Superapp Moçambique</title>")
troca("#erpLoad{","body.app-on #fbar,body.app-on #stats,body.app-on #list,body.app-on #pg,body.app-on #ixp,body.app-on #bday,body.app-on #alerts,body.app-on main>.sub,body.app-on .leadnav,body.app-on #bSet{display:none!important}\n#erpLoad{")
# lançamentos do histórico (forma de pagamento por confirmar) não mexem no caixa nem nos bancos
troca("function delta(x){const v=+x.valor||0,din=isCash(x.fp);","function delta(x){if(x.fp==='Histórico Eticadata')return[0,0];const v=+x.valor||0,din=isCash(x.fp);")
troca("k=isCash(x.fp)?s.din:s.ban;","k=isCash(x.fp)?s.din:x.fp==='Histórico Eticadata'?{vE:0,vS:0,lev:0,dep:0}:s.ban;")
open(S+'/superapp/index.html','w',encoding='utf-8').write(s)
print('index.html',os.path.getsize(S+'/superapp/index.html'))
