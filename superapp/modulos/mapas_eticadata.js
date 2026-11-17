// ---- Mapas do Eticadata (Diário de Vendas + Mapa de Caixa): importação diária, conferência e lançamento no Financeiro
const ETI_VEND={'2':'Guacha','7':'Damião'};
const ETI_FP={'Dinheiro':'Dinheiro','Ponto 24':'Cartão / POS','M-Pesa':'M-Pesa','e-Mola':'e-Mola','mKesh':'mKesh','Cheque':'Cheque','Transferência':'Transferência bancária'};
const ENUM='-?\\d{1,3}(?:\\.\\d{3})*,\\d{2}';
const eN=s=>+String(s).replace(/\./g,'').replace(',','.');
const eD=s=>{const p=String(s).split('/');return p[2]+'-'+p[1]+'-'+p[0]};
const m2=v=>(+v||0).toLocaleString('pt-PT',{minimumFractionDigits:2,maximumFractionDigits:2})+' MT';
const eVn=c=>ETI_VEND[c]?ETI_VEND[c]+' ('+c+')':'Vendedor '+c;
function etiDiario(t){
 const re=new RegExp('(\\d{2}/\\d{2}/\\d{4})\\s+([A-Z]{1,4}/[A-Z]{1,6}\\s+\\d{4}-\\d{3,})\\s+(\\d+)\\s+([^\\d\\-][^\\n]*?)\\s+('+ENUM+')\\s+('+ENUM+')\\s+('+ENUM+')\\s+('+ENUM+')\\s+('+ENUM+')\\s+('+ENUM+')\\s+('+ENUM+')','g');
 const docs=[],vis=new Set();let m;
 while((m=re.exec(t))){const doc=m[2].replace(/\s+/g,' ');if(vis.has(doc))continue;vis.add(doc);
  docs.push({data:eD(m[1]),doc,vend:m[3],meio:m[4].trim(),merc:eN(m[5]),desc:eN(m[6]),imp:eN(m[7]),tot:eN(m[9])})}
 const imp=[],q=t.match(new RegExp('Quadro Resumo d[oe]s? Impostos[\\s\\S]*?Taxa\\s+((?:\\d+\\s+'+ENUM+'\\s+'+ENUM+'\\s+'+ENUM+'\\s*)+)'));
 if(q){const r=new RegExp('(\\d+)\\s+('+ENUM+')\\s+('+ENUM+')\\s+('+ENUM+')','g');let x;while((x=r.exec(q[1])))imp.push({cod:x[1],taxa:eN(x[2]),inc:eN(x[3]),iva:eN(x[4])})}
 const sum=k=>Math.round(docs.reduce((s,d)=>s+d[k],0)*100)/100;
 return {docs,tot:sum('tot'),desc:sum('desc'),imp}}
function etiCaixa(t){
 const g=r=>{const m=t.match(r);return m?m[1]:null},data=g(/Data:\s*(\d{2}\/\d{2}\/\d{4})/),
  ab=t.match(new RegExp('Abertura de Caixa Num\\.:\\s*(\\S+)[\\s\\S]*?('+ENUM+')')),mov={},
  b=t.match(/Movimentos do Dia[\s\S]*?Cheques-Oferta\s+([\s\S]*?)\s+Soma:/);
 // "5.462,00 Dinheiro 22.431,00 Ponto 24": o nome do meio pode ter algarismos, mas não vírgula decimal
 if(b){const r=new RegExp('('+ENUM+')\\s+(.+?)(?=\\s+'+ENUM+'|\\s*$)','g'),s=b[1].trim();let x;while((x=r.exec(s)))mov[x[2].trim()]=eN(x[1])}
 const f=t.split('Fecho do Caixa').pop(),res={};
 ['Vendas Anuladas','Devoluções','Vendas','Descontos','Nº Vendas','Venda Média','Sinal Encomendas','Vendas a Crédito','Recebimentos','Vales Emitidos','Vales Recebidos'].forEach(k=>{
  const m=f.match(new RegExp('(?:^|\\s)'+k.replace(/[.*+?^${}()|[\]\\/]/g,'\\$&')+'\\s+('+ENUM+')'));if(m)res[k]=eN(m[1])});
 return {data:data?eD(data):null,posto:g(/Posto:\s*(\S+)/),abNum:ab?ab[1]:null,fundo:ab?eN(ab[2]):null,mov,
  totMov:Math.round(Object.values(mov).reduce((s,v)=>s+v,0)*100)/100,res}}
function etiConf(d,c){const a=[],ok=(x,y)=>Math.abs(x-y)<.01;if(!c)return a;
 if(c.res['Vendas']!=null&&!ok(c.res['Vendas'],d.tot))a.push('Vendas no caixa '+m2(c.res['Vendas'])+' ≠ total dos documentos '+m2(d.tot));
 if(!ok(c.totMov,d.tot))a.push('Movimentos do caixa '+m2(c.totMov)+' ≠ total dos documentos '+m2(d.tot));
 if(c.res['Nº Vendas']!=null&&Math.round(c.res['Nº Vendas'])!==d.docs.length)a.push('Nº de vendas no caixa '+Math.round(c.res['Nº Vendas'])+' ≠ '+d.docs.length+' documentos no diário');
 if(c.res['Descontos']!=null&&!ok(c.res['Descontos'],Math.abs(d.desc)))a.push('Descontos no caixa '+m2(c.res['Descontos'])+' ≠ '+m2(Math.abs(d.desc))+' no diário');
 const ds=[...new Set(d.docs.map(x=>x.data))];if(c.data&&ds.length&&(ds.length>1||ds[0]!==c.data))a.push('Datas diferentes: caixa '+fdt(c.data)+', diário '+ds.map(fdt).join(', '));
 return a}
let etiLib=null;
async function etiPdf(file){
 if(!etiLib){await new Promise((ok,ko)=>{const s=document.createElement('script');s.src='https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';s.onload=ok;s.onerror=()=>ko(new Error('Leitor de PDF indisponível (sem internet). Cole o texto do PDF.'));document.head.appendChild(s)});
  etiLib=window.pdfjsLib;etiLib.GlobalWorkerOptions.workerSrc='https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js'}
 const pdf=await etiLib.getDocument({data:await file.arrayBuffer()}).promise;let t='';
 for(let i=1;i<=pdf.numPages;i++){const c=await(await pdf.getPage(i)).getTextContent();t+=c.items.map(x=>x.str).join(' ')+'\n'}
 return t}
let etiT={d:'',c:''};
function etiTab(o){const e=Object.entries(o).sort((a,b)=>b[1]-a[1]);return e.length?'<div class="tw"><table>'+e.map(([k,v])=>'<tr><td>'+esc(k)+'</td><td class="r">'+m2(v)+'</td></tr>').join('')+'</table></div>':'<p class="m">—</p>'}
function R_me(){D.mapas=D.mapas||[];
 const d=etiT.d?etiDiario(etiT.d):null,c=etiT.c?etiCaixa(etiT.c):null,av=d&&c?etiConf(d,c):[];
 let h='<div class="card"><b>📥 Mapas do Eticadata — vendas do dia</b><p class="m">O Eticadata continua a ser o sistema fiscal (é lá que se emitem os documentos V/DIN). Aqui entra o resumo que a loja envia às 18h: o <b>Diário de Vendas</b> (DiarioVendas dd.mm.pdf) e o <b>Mapa de Caixa</b> (Caixa dd.mm.pdf). Os dois são conferidos antes de gravar.</p>'+
  '<div class="row"><label class="m">📄 Diário de Vendas (PDF) <input type="file" accept="application/pdf" data-lme="fd"></label><label class="m">📄 Mapa de Caixa (PDF) <input type="file" accept="application/pdf" data-lme="fc"></label></div>'+
  '<details style="margin-top:8px"'+(etiT.d||etiT.c?' open':'')+'><summary class="m">Ou colar o texto dos PDFs</summary><textarea id="lMeD" placeholder="Texto do Diário de Vendas">'+esc(etiT.d)+'</textarea><textarea id="lMeC" placeholder="Texto do Mapa de Caixa">'+esc(etiT.c)+'</textarea><div class="row"><button data-lb2="mel">Ler texto</button><button data-lb2="mex">Limpar</button></div></details></div>';
 if(d||c){
  const dia=(c&&c.data)||(d&&d.docs[0]&&d.docs[0].data)||'',pv={},pm={};
  if(d)d.docs.forEach(x=>{pv[eVn(x.vend)]=(pv[eVn(x.vend)]||0)+x.tot;pm[x.meio]=(pm[x.meio]||0)+x.tot});
  const ivaT=d?d.imp.reduce((s,x)=>s+x.iva,0):0,pode=d&&c&&d.docs.length&&!av.length;
  h+='<div class="card"><b>Dia '+fdt(dia)+(c&&c.posto?' · posto '+esc(c.posto):'')+'</b><div class="k">'+
   (d?kc('Documentos (vendas)',d.docs.length)+kc('Total vendido',m2(d.tot),'pos')+kc('Descontos',m2(Math.abs(d.desc)))+kc('IVA incluído',m2(ivaT))+kc('Venda média',m2(d.docs.length?d.tot/d.docs.length:0)):kc('Diário de Vendas','em falta','neg'))+
   (c?kc('Fundo de caixa',m2(c.fundo))+kc('Abertura nº',esc(c.abNum||'—')):kc('Mapa de Caixa','em falta','neg'))+'</div>'+
   (d&&c?(av.length?'<p class="note">⚠ Os mapas não batem — nada será gravado:</p><ul>'+av.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'<p style="color:var(--wa)">✅ Diário de Vendas e Mapa de Caixa batem certo (total, nº de vendas, descontos e meios de pagamento).</p>'):'<p class="m">Junte os dois mapas do mesmo dia para conferir e gravar.</p>')+
   '<div class="row"><button class="p" data-lb2="mef"'+(pode?'':' disabled')+'>💾 Gravar e lançar no Financeiro</button><button data-lb2="mes"'+(pode?'':' disabled')+'>Só gravar o mapa</button></div></div>'+
   '<div class="card"><b>Por meio de pagamento</b>'+(c?'<p class="m">Mapa de Caixa (os pagamentos mistos já vêm divididos):</p>'+etiTab(c.mov):'')+(d?'<p class="m">Diário de Vendas (por documento):</p>'+etiTab(pm):'')+'</div>'+
   (d?'<div class="card"><b>Por vendedor</b>'+etiTab(pv)+'</div><div class="card"><b>Quadro de impostos</b><div class="tw"><table><tr><th>Código</th><th class="r">Taxa</th><th class="r">Incidência</th><th class="r">IVA</th></tr>'+d.imp.map(x=>'<tr><td>'+esc(x.cod)+(x.taxa?'':' (isento)')+'</td><td class="r">'+x.taxa+' %</td><td class="r">'+m2(x.inc)+'</td><td class="r">'+m2(x.iva)+'</td></tr>').join('')+'</table></div></div>'+
    '<div class="card"><b>Documentos</b><div class="tw"><table><tr><th>Documento</th><th>Vendedor</th><th>Meio</th><th class="r">Descontos</th><th class="r">Total</th></tr>'+d.docs.map(x=>'<tr><td>'+esc(x.doc)+'</td><td>'+esc(eVn(x.vend))+'</td><td>'+esc(x.meio)+'</td><td class="r">'+(x.desc?m2(x.desc):'')+'</td><td class="r">'+m2(x.tot)+'</td></tr>').join('')+'</table></div></div>':'')}
 const H=D.mapas.slice().sort((a,b)=>a.data<b.data?1:-1),mes=hoje().slice(0,7),MM=H.filter(x=>x.data.slice(0,7)===mes),tm=MM.reduce((s,x)=>s+x.tot,0),nm=MM.reduce((s,x)=>s+x.n,0);
 const meios=[...new Set(H.flatMap(x=>Object.keys(x.mov||{})))];
 h+='<div class="card"><b>Dias importados</b><div class="k">'+kc('Este mês ('+MM.length+' dias)',m2(tm),'pos')+kc('Vendas no mês',nm)+kc('Venda média do mês',m2(nm?tm/nm:0))+'</div><div class="tw"><table><tr><th>Dia</th><th class="r">Vendas</th><th class="r">Total</th>'+meios.map(k=>'<th class="r">'+esc(k)+'</th>').join('')+'<th>Financeiro</th><th></th></tr>'+
  (H.length?H.slice(0,62).map(x=>'<tr><td>'+fdt(x.data)+'</td><td class="r">'+x.n+'</td><td class="r">'+m2(x.tot)+'</td>'+meios.map(k=>'<td class="r">'+((x.mov||{})[k]?m2(x.mov[k]):'')+'</td>').join('')+'<td>'+(x.fin?'✅ lançado':'—')+'</td><td><button data-lb2="med" data-i="'+x.data+'" title="Apagar este dia">🗑</button></td></tr>').join(''):'<tr><td colspan="'+(5+meios.length)+'" class="m">Ainda nenhum dia importado.</td></tr>')+'</table></div></div>';
 return h}
VIEW.me=R_me;TABS.push(['me','📥 Mapas do Eticadata']);
// Fecho de caixa (Z): conferência com o Mapa de Caixa do Eticadata do mesmo dia
{const _Rfc=VIEW.fc;VIEW.fc=()=>{const m=(D.mapas||[]).find(x=>x.data===fcD);
 return _Rfc()+'<div class="card"><b>Conferência com o Eticadata</b>'+(m?'<p class="m">Mapa de Caixa nº '+esc(m.abNum||'—')+' · posto '+esc(m.posto||'—')+'</p><div class="k">'+kc('Vendas no Eticadata',m2(m.tot),'pos')+kc('Nº de vendas',m.n)+kc('Venda média',m2(m.n?m.tot/m.n:0))+kc('Descontos',m2(Math.abs(m.desc||0)))+kc('Fundo de caixa',m2(m.fundo))+'</div>'+etiTab(m.mov||{})+
  '<p class="m">Dinheiro esperado na gaveta = fundo de caixa + vendas em dinheiro: <b>'+m2((m.fundo||0)+((m.mov||{})['Dinheiro']||0))+'</b></p>':'<p class="m">Ainda não há Mapa de Caixa do Eticadata para '+fdt(fcD)+'. Importe-o em <b>📥 Mapas do Eticadata</b>.</p>')+'</div>'}}
document.addEventListener('click',async e=>{const b=e.target.closest('#liv [data-lb2]');if(!b||b.disabled)return;const a=b.dataset.lb2;
 if(a==='mel'){etiT.d=$l('lMeD').value;etiT.c=$l('lMeC').value;render();return}
 if(a==='mex'){etiT={d:'',c:''};render();return}
 if(a==='med'){if(!confirm('Apagar o mapa do dia '+fdt(b.dataset.i)+'? (As entradas lançadas no Financeiro também saem.)'))return;
  D.mapas=(D.mapas||[]).filter(x=>x.data!==b.dataset.i);if(window.FIN){const F=await FIN.get();for(const m of (F.mov||[]).filter(m=>String(m.id).indexOf('eti-'+b.dataset.i)===0))await FIN.delMov(m.id)}
  save();render();return}
 if(a==='mes'||a==='mef'){const d=etiDiario(etiT.d),c=etiCaixa(etiT.c),av=etiConf(d,c);
  if(!d.docs.length){toast('Nenhum documento reconhecido no Diário de Vendas.',1);return}
  if(av.length){toast('Os mapas não batem — nada foi gravado.',1);return}
  const dia=c.data||d.docs[0].data,porVend={};d.docs.forEach(x=>porVend[x.vend]=(porVend[x.vend]||0)+x.tot);
  const reg={data:dia,n:d.docs.length,tot:d.tot,desc:d.desc,fundo:c.fundo,posto:c.posto,abNum:c.abNum,mov:c.mov,porVend,imp:d.imp,
   docs:d.docs.map(x=>[x.doc,x.vend,x.meio,x.tot]),em:new Date().toISOString(),fin:false};
  if(a==='mef'&&window.FIN){const F=await FIN.get(),ja=(F.mov||[]).filter(m=>m.data===dia&&m.tipo==='E'&&String(m.cat).indexOf('Vendas')===0&&String(m.id).indexOf('eti-')!==0);
   const dup=ja.length&&!confirm('Já há '+ja.length+' entrada(s) de vendas no Financeiro em '+fdt(dia)+' ('+m2(ja.reduce((s,m)=>s+m.valor,0))+').\nLançar também o Eticadata? Pode ficar em duplicado.\n\nOK = lançar · Cancelar = só gravar o mapa');
   if(!dup){for(const m of (F.mov||[]).filter(m=>String(m.id).indexOf('eti-'+dia+'-')===0))await FIN.delMov(m.id);
    await FIN.addMany(Object.entries(c.mov).filter(([,v])=>v>0).map(([meio,v])=>({id:'eti-'+dia+'-'+meio.replace(/[^A-Za-z0-9]+/g,''),data:dia,tipo:'E',cat:'Vendas — balcão',
     parte:'Eticadata · Mapa de Caixa'+(c.posto?' '+c.posto:''),fp:ETI_FP[meio]||meio,valor:v,nota:'Mapa de Caixa nº '+(c.abNum||'')+' · '+d.docs.length+' vendas'})));reg.fin=true}}
  D.mapas=(D.mapas||[]).filter(x=>x.data!==dia);D.mapas.push(reg);save();etiT={d:'',c:''};
  toast('Dia '+fdt(dia)+' gravado'+(reg.fin?' e lançado no Financeiro':'')+'.');render()}});
document.addEventListener('change',async e=>{const t=e.target;if(!t.dataset||!t.dataset.lme||!t.files||!t.files[0])return;
 try{toast('A ler o PDF…');const s=await etiPdf(t.files[0]);if(t.dataset.lme==='fd')etiT.d=s;else etiT.c=s;render()}catch(x){toast(x.message||'Não foi possível ler o PDF.',1)}});
