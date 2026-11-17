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

# ---- cartão corporativo: movimentos do Oreate (CC_MONTH) carregados sozinhos; editáveis; os apagados/editados não voltam
ccore=open(S+'/cc_oreate.json',encoding='utf-8').read().replace('</','<\\/')
s=s.replace('<script id="histData" type="application/json">','<script id="ccOre" type="application/json">'+ccore+'</script>\n<script id="histData" type="application/json">')
troca("function ccNovo(pre){pre=pre||{};const cats=window.FIN?FIN.CCAT:[];ask('Movimento do cartão corporativo',[{k:'t',l:'Tipo',t:'select',o:Object.values(CCT),v:CCT[pre.t||'R']},{k:'data',l:'Data',t:'date',v:hoje()},",
 "function ccNovo(pre,ed){pre=pre||{};const cats0=window.FIN?FIN.CCAT:[],cats=pre.cat&&!cats0.includes(pre.cat)?cats0.concat([pre.cat]):cats0;ask(ed?'Editar movimento do cartão':'Movimento do cartão corporativo',[{k:'t',l:'Tipo',t:'select',o:Object.values(CCT),v:CCT[pre.t||'R']},{k:'data',l:'Data',t:'date',v:pre.data||hoje()},")
troca("{k:'cat',l:'Categoria da despesa (para gasto no cartão / em dinheiro)',t:'select',o:cats,v:'Outras despesas da loja'},","{k:'cat',l:'Categoria da despesa (para gasto no cartão / em dinheiro)',t:'select',o:cats,v:pre.cat||'Outras despesas da loja'},")
troca("{k:'lanc',l:'Recarga: lançar a saída do banco no Financeiro?',t:'select',o:['Sim','Não (já está lançada)'],v:'Sim'}],","{k:'lanc',l:'Recarga: lançar a saída do banco no Financeiro?',t:'select',o:['Sim','Não (já está lançada)'],v:ed?'Não (já está lançada)':'Sim'}],")
troca("  const x={id:uid(),t,data:o.data,v:num(o.v),d:o.d.trim(),cat:(t==='G'||t==='D')?o.cat:''};",
 "  if(ed){const x=(D.cc||[]).find(y=>y.id===ed.id);if(x){Object.assign(x,{t,data:o.data,v:num(o.v),d:o.d.trim(),cat:(t==='G'||t==='D')?o.cat:'',ed:new Date().toISOString()});if(x.fid&&window.FIN)await FIN.updMov(x.fid,{data:x.data,valor:x.v,ed:x.ed})}await saveNow();render();return}\n  const x={id:uid(),t,data:o.data,v:num(o.v),d:o.d.trim(),cat:(t==='G'||t==='D')?o.cat:''};")
troca("<td><button data-lb=\"ccx\" data-i=\"'+x.id+'\">🗑</button></td></tr>')","<td style=\"white-space:nowrap\"><button data-lb=\"cce\" data-i=\"'+x.id+'\" title=\"Editar\">✏️</button><button data-lb=\"ccx\" data-i=\"'+x.id+'\" title=\"Apagar\">🗑</button>'+(x.ed?' <small class=\"m\" title=\"Editado à mão\">✎</small>':'')+(x.src==='oreate'?' <small class=\"m\" title=\"Importado do app Oreate (total do mês)\">ⓞ</small>':'')+'</td></tr>')")
troca("const b=e.target.closest('#liv [data-lb=ccn],#liv [data-lb=ccx],","const b=e.target.closest('#liv [data-lb=ccn],#liv [data-lb=cce],#liv [data-lb=ccx],")
troca(" if(a==='ccx'){if(confirm('Apagar este movimento?')){const x=D.cc.find(y=>y.id===b.dataset.i);D.cc=D.cc.filter(y=>y.id!==b.dataset.i);",
 " if(a==='cce'){const x=(D.cc||[]).find(y=>y.id===b.dataset.i);if(x)ccNovo(x,x);return}\n if(a==='ccx'){if(confirm('Apagar este movimento?')){const x=D.cc.find(y=>y.id===b.dataset.i);if(x&&String(x.id).indexOf('ore-cc-')===0)(D.ccDel=D.ccDel||[]).push(x.id);D.cc=D.cc.filter(y=>y.id!==b.dataset.i);")
CCAUTO="""// cartão corporativo: movimentos do Oreate entram sozinhos (uma vez); as recargas lançam a saída do banco no Financeiro
async function ccOreAuto(){await init();const L=JSON.parse(document.getElementById('ccOre').textContent||'[]');D.cc=D.cc||[];const del=D.ccDel||[],tem=new Set(D.cc.map(x=>x.id));let n=0;
 for(const y of L){if(tem.has(y.id)||del.includes(y.id))continue;const x=Object.assign({},y);
  if(x.t==='R'&&window.FIN){x.fid='ore-ccfin-'+x.id.slice(7);const F=await FIN.get();if(!(F.mov||[]).some(m=>m.id===x.fid))await FIN.add({id:x.fid,data:x.data,tipo:'S',cat:'Recarga do cartão corporativo',parte:'Cartão corporativo',fp:'Transferência bancária',valor:x.v,nota:x.d})}
  D.cc.push(x);n++}
 if(n){await saveNow();toast('Cartão corporativo: '+n+' movimentos do Oreate carregados (jul/2022 – ago/2026).');render()}}
setTimeout(()=>ccOreAuto().catch(e=>console.warn('ccOreAuto',e)),2500);"""
troca("const CCT={R:'Recarga (banco → cartão)',",CCAUTO+"\nconst CCT={R:'Recarga (banco → cartão)',")

# ---- borderôs (2022–2024) e SWIFTs (2019–2026) como saídas do banco; entram uma vez; editáveis; os apagados não voltam
fbs=open(S+'/fin_brd_swf.json',encoding='utf-8').read().replace('</','<\\/')
s=s.replace('<script id="histData" type="application/json">','<script id="finBrd" type="application/json">'+fbs+'</script>\n<script id="histData" type="application/json">')
troca("if(confirm('Apagar este lançamento?')){F.mov=F.mov.filter(x=>x.id!==i);","if(confirm('Apagar este lançamento?')){if(/^(brd-|swf-|ore-ccfin-)/.test(i)){F.cfg.delImp=F.cfg.delImp||[];F.cfg.delImp.push(i)}F.mov=F.mov.filter(x=>x.id!==i);")
FBAUTO="""// saídas do banco vindas dos borderôs do e-mail e dos SWIFTs do BCI (carregadas uma vez)
async function finBrdAuto(){await init();if(!window.FIN)return;const L=JSON.parse(document.getElementById('finBrd').textContent||'[]'),F=await FIN.get(),del=(FIN.cfg().delImp||[]),tem=new Set((F.mov||[]).map(m=>m.id));
 const novos=L.filter(x=>!tem.has(x.id)&&!del.includes(x.id));if(novos.length){await FIN.addMany(novos);toast('Financeiro: '+novos.length+' saídas do banco carregadas (borderôs 2022–2024 e SWIFTs 2019–2026).');render()}}
setTimeout(()=>finBrdAuto().catch(e=>console.warn('finBrdAuto',e)),3500);"""
troca("// cartão corporativo: movimentos do Oreate entram sozinhos",FBAUTO + "\n// cartão corporativo: movimentos do Oreate entram sozinhos")

# ---- saídas do banco com categoria «Recarga do cartão corporativo» entram sozinhas no saldo do cartão (sem duplicar as que já têm movimento ligado)
troca("function ccCalc(){const L=(D.cc||[]).slice()","function ccAll(){const L=(D.cc||[]).slice(),lig=new Set(L.map(x=>x.fid).filter(Boolean)),F=window.FIN&&FIN.peek?FIN.peek():null;\n (F&&F.mov||[]).forEach(m=>{if(m.tipo==='S'&&m.cat==='Recarga do cartão corporativo'&&!lig.has(m.id)&&m.data)L.push({id:'fin:'+m.id,t:'R',data:String(m.data),v:+m.valor||0,d:(m.nota||'Recarga lançada no Financeiro'),cat:'',src:'fin'})});return L}\nfunction ccCalc(){const L=ccAll()")
troca("function R_cc(){const L=(D.cc||[]),all=ccCalc()","function R_cc(){const L=ccAll(),all=ccCalc()")
troca("'+mz(x.v)+'</td><td style=\"white-space:nowrap\"><button data-lb=\"cce\"","'+mz(x.v)+'</td><td style=\"white-space:nowrap\">'+(x.src==='fin'?'<small class=\"m\" title=\"Saída do banco lançada no Financeiro; edite lá\">🏦 do Financeiro</small>':'<button data-lb=\"cce\"")
troca("(x.src==='oreate'?' <small class=\"m\" title=\"Importado do app Oreate (total do mês)\">ⓞ</small>':'')+'</td></tr>')","(x.src==='oreate'?' <small class=\"m\" title=\"Importado do app Oreate (total do mês)\">ⓞ</small>':''))+'</td></tr>')")

open(S+'/superapp/index.html','w',encoding='utf-8').write(s)
print('index.html',os.path.getsize(S+'/superapp/index.html'))
