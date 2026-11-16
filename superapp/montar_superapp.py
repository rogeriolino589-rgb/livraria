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
AUTO="""// mapas do e-mail: gravados sozinhos ao abrir o superapp, só se o Diário e o Caixa baterem certo e o dia não tiver outras vendas lançadas
async function etiAuto(){await init();if(!window.FIN)return;D.mapas=D.mapas||[];const feitos=[];
 for(const x of etiPend()){if(D.mapas.some(m=>m.data===x.data)||!x.d||!x.c)continue;
  let d,c;try{d=etiDiario(x.d);c=etiCaixa(x.c)}catch(e){continue}
  if(!d||!c||!d.docs||!d.docs.length||etiConf(d,c).length)continue;
  const dia=c.data||d.docs[0].data,F=await FIN.get();
  if((F.mov||[]).some(m=>m.data===dia&&m.tipo==='E'&&String(m.cat).indexOf('Vendas')===0&&(m.ed||String(m.id).indexOf('eti-')!==0&&String(m.id).indexOf('hist-')!==0)))continue;
  for(const m of (F.mov||[]).filter(m=>!m.ed&&(String(m.id).indexOf('eti-'+dia+'-')===0||String(m.id).indexOf('hist-'+dia+'-')===0)))await FIN.delMov(m.id);
  await FIN.addMany(Object.entries(c.mov).filter(([,v])=>v>0).map(([meio,v])=>({id:'eti-'+dia+'-'+meio.replace(/[^A-Za-z0-9]+/g,''),data:dia,tipo:'E',cat:'Vendas — balcão',
   parte:'Eticadata · Mapa de Caixa'+(c.posto?' '+c.posto:''),fp:ETI_FP[meio]||meio,valor:v,nota:'Mapa de Caixa nº '+(c.abNum||'')+' · '+d.docs.length+' vendas · e-mail da loja'})));
  const porVend={};d.docs.forEach(y=>porVend[y.vend]=(porVend[y.vend]||0)+y.tot);
  D.mapas.push({data:dia,n:d.docs.length,tot:d.tot,desc:d.desc,fundo:c.fundo,posto:c.posto,abNum:c.abNum,mov:c.mov,porVend,imp:d.imp,
   docs:d.docs.map(y=>[y.doc,y.vend,y.meio,y.tot]),em:new Date().toISOString(),fin:true,auto:true});feitos.push(fdt(dia))}
 if(feitos.length){save();toast('Vendas do e-mail gravadas no Financeiro: '+feitos.join(', ')+'.');render()}}
setTimeout(()=>etiAuto().catch(e=>console.warn('etiAuto',e)),1500);"""
troca("let etiT={d:'',c:''};","let etiT={d:'',c:''};\nfunction etiPend(){try{return JSON.parse(document.getElementById('etiPend').textContent||'[]')}catch(e){return[]}}\n"+AUTO)
troca(" if(a==='mex'){etiT={d:'',c:''};render();return}"," if(a==='mex'){etiT={d:'',c:''};render();return}\n if(a==='mep'){const x=etiPend().find(x=>x.data===b.dataset.i);if(x){etiT={d:x.d,c:x.c};render()}return}")
# o mapa do dia substitui as entradas do histórico (Análise de Vendas) desse dia; não conta como duplicado
troca("String(m.cat).indexOf('Vendas')===0&&String(m.id).indexOf('eti-')!==0);","String(m.cat).indexOf('Vendas')===0&&(m.ed||String(m.id).indexOf('eti-')!==0&&String(m.id).indexOf('hist-')!==0));")
troca("if(!dup){for(const m of (F.mov||[]).filter(m=>String(m.id).indexOf('eti-'+dia+'-')===0))await FIN.delMov(m.id);","if(!dup){for(const m of (F.mov||[]).filter(m=>!m.ed&&(String(m.id).indexOf('eti-'+dia+'-')===0||String(m.id).indexOf('hist-'+dia+'-')===0)))await FIN.delMov(m.id);")
s=s.replace('<script id="histData" type="application/json">','<script id="etiPend" type="application/json">'+json.dumps(pend,ensure_ascii=False).replace('</','<\\/')+'</script>\n<script id="histData" type="application/json">')
# ---- lançamentos editáveis (antigos e novos); os editados à mão ficam protegidos das importações
troca("function novo(tipo,pre){tipoCur=tipo||'E';const cats=()=>tipoCur==='E'?ENT:tipoCur==='S'?SAI:TRF;\n ask('Novo lançamento',",
 "function novo(tipo,pre,ed){tipoCur=tipo||'E';const cats=()=>tipoCur==='E'?ENT:tipoCur==='S'?SAI:TRF;const fpo=pre&&pre.fp&&!FP.includes(pre.fp)?FP.concat([pre.fp]):FP;\n ask(ed?'Editar lançamento':'Novo lançamento',")
troca("{k:'data',l:'Data',t:'date',v:hoje()},{k:'cat',l:'Categoria',t:'select',o:cats(),v:pre&&pre.cat},","{k:'data',l:'Data',t:'date',v:pre&&pre.data||hoje()},{k:'cat',l:'Categoria',t:'select',o:pre&&pre.cat&&!cats().includes(pre.cat)?cats().concat([pre.cat]):cats(),v:pre&&pre.cat},")
troca("{k:'fp',l:'Forma de pagamento',t:'select',o:FP,v:pre&&pre.fp}","{k:'fp',l:'Forma de pagamento',t:'select',o:fpo,v:pre&&pre.fp}")
troca("const lista=t==='E'?ENT:t==='S'?SAI:TRF,cat=lista.includes(o.cat)?o.cat:lista[0];\n  F.mov.push({id:uid(),data:o.data||hoje(),tipo:t,cat,parte:o.parte,fp:t==='T'?'—':o.fp,valor:v,nota:o.nota});save();render()});",
 "const lista=t==='E'?ENT:t==='S'?SAI:TRF,cat=lista.includes(o.cat)||(ed&&o.cat===ed.cat)?o.cat:lista[0];\n  if(ed){const x=F.mov.find(m=>m.id===ed.id);if(x){Object.assign(x,{data:o.data||x.data,tipo:t,cat,parte:o.parte,fp:t==='T'?'—':o.fp,valor:v,nota:o.nota,ed:new Date().toISOString()})}save();render();return}\n  F.mov.push({id:uid(),data:o.data||hoje(),tipo:t,cat,parte:o.parte,fp:t==='T'?'—':o.fp,valor:v,nota:o.nota});save();render()});")
troca("<td><button data-fa=\"del\" data-i=\"'+x.id+'\">🗑</button></td></tr>'}","<td style=\"white-space:nowrap\"><button data-fa=\"ed\" data-i=\"'+x.id+'\" title=\"Editar\">✏️</button><button data-fa=\"del\" data-i=\"'+x.id+'\" title=\"Apagar\">🗑</button>'+(x.ed?' <small class=\"m\" title=\"Editado à mão: as importações não o substituem\">✎</small>':'')+'</td></tr>'}")
troca(" else if(a==='del'){if(confirm('Apagar este lançamento?')){F.mov=F.mov.filter(x=>x.id!==i);save();render()}}",
 " else if(a==='del'){if(confirm('Apagar este lançamento?')){F.mov=F.mov.filter(x=>x.id!==i);save();render()}}\n else if(a==='ed'){const x=F.mov.find(m=>m.id===i);if(x)novo(x.tipo,x,x)}")
open(S+'/superapp/index.html','w',encoding='utf-8').write(s)
print('index.html',os.path.getsize(S+'/superapp/index.html'))
