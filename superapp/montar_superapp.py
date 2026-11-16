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
troca("function delta(x){const v=+x.valor||0,din=isCash(x.fp);","function delta(x){if(String(x.id).indexOf('hist-')===0)return[0,0];const v=+x.valor||0,din=isCash(x.fp);")
troca("k=isCash(x.fp)?s.din:s.ban;","k=String(x.id).indexOf('hist-')===0?{vE:0,vS:0,lev:0,dep:0}:isCash(x.fp)?s.din:s.ban;")
# mapas recebidos por e-mail (Diário de Vendas + Mapa de Caixa) prontos a carregar no módulo «Mapas do Eticadata»
import glob,json
pend=[]
for f in sorted(glob.glob(S+'/mapas_email/*_diario.txt')):
    dia=os.path.basename(f)[:10];c=f.replace('_diario.txt','_caixa.txt')
    pend.append({'data':dia,'d':open(f,encoding='utf-8').read(),'c':open(c,encoding='utf-8').read() if os.path.exists(c) else ''})
troca(" let h='<div class=\"card\"><b>📥 Mapas do Eticadata — vendas do dia</b>",
 " const pe=etiPend().filter(x=>!D.mapas.some(m=>m.data===x.data));\n let h=(pe.length&&!etiT.d?'<div class=\"card\" style=\"border-color:var(--ac)\"><b>📧 Mapas recebidos por e-mail</b><p class=\"m\">Lidos do e-mail «Resumo de vendas diário» da loja. Carregue para conferir e gravar.</p>'+pe.map(x=>'<button class=\"b\" data-lb2=\"mep\" data-i=\"'+x.data+'\">📥 '+fdt(x.data)+'</button> ').join('')+'</div>':'')+'<div class=\"card\"><b>📥 Mapas do Eticadata — vendas do dia</b>")
troca("let etiT={d:'',c:''};","let etiT={d:'',c:''};\nfunction etiPend(){try{return JSON.parse(document.getElementById('etiPend').textContent||'[]')}catch(e){return[]}}")
troca(" if(a==='mex'){etiT={d:'',c:''};render();return}"," if(a==='mex'){etiT={d:'',c:''};render();return}\n if(a==='mep'){const x=etiPend().find(x=>x.data===b.dataset.i);if(x){etiT={d:x.d,c:x.c};render()}return}")
# o mapa do dia substitui as entradas do histórico (Análise de Vendas) desse dia; não conta como duplicado
troca("String(m.cat).indexOf('Vendas')===0&&String(m.id).indexOf('eti-')!==0);","String(m.cat).indexOf('Vendas')===0&&String(m.id).indexOf('eti-')!==0&&String(m.id).indexOf('hist-')!==0);")
troca("if(!dup){for(const m of (F.mov||[]).filter(m=>String(m.id).indexOf('eti-'+dia+'-')===0))await FIN.delMov(m.id);","if(!dup){for(const m of (F.mov||[]).filter(m=>String(m.id).indexOf('eti-'+dia+'-')===0||String(m.id).indexOf('hist-'+dia+'-')===0))await FIN.delMov(m.id);")
s=s.replace('<script id="histData" type="application/json">','<script id="etiPend" type="application/json">'+json.dumps(pend,ensure_ascii=False).replace('</','<\\/')+'</script>\n<script id="histData" type="application/json">')
open(S+'/superapp/index.html','w',encoding='utf-8').write(s)
print('index.html',os.path.getsize(S+'/superapp/index.html'))
