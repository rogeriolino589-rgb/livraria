// ---- Histórico de vendas (Eticadata ERP19 + ERP22) e assistente Roger
let HV=null;
function hvDados(){if(HV)return HV;try{HV=JSON.parse(document.getElementById('histData').textContent)}catch(e){HV={dias:[],zonas:[],tipos:[],artigos:[],artigosVend:{},gerado:''}}return HV}
const hvM2=v=>(+v||0).toLocaleString('pt-PT',{minimumFractionDigits:2,maximumFractionDigits:2})+' MT';
const hvPc=(a,b)=>b?Math.round(a*1000/b)/10+'%':'—';
let hvS={ano:'',vend:'',q:''};
function hvAgg(rows,key){const m=new Map();for(const r of rows){const k=key(r);let g=m.get(k);if(!g){g={n:0,v:0,va:0,at:0,nd:0};m.set(k,g)}g.n+=r[3];g.v+=r[4];g.va+=r[5];g.at+=r[6];g.nd+=r[7]}return m}
function hvFiltrar(o){const H=hvDados(),v=(o.vendedor||'').toLowerCase();return H.dias.filter(r=>(!o.de||r[0]>=o.de)&&(!o.ate||r[0]<=o.ate)&&(!v||r[2].toLowerCase().includes(v)))}
function hvLinha(k,g){const t=g.va+g.at+g.nd;return '<tr><td>'+esc(k)+'</td><td class="r">'+g.n.toLocaleString('pt-PT')+'</td><td class="r">'+hvM2(g.v)+'</td><td class="r">'+(g.n?hvM2(g.v/g.n):'—')+'</td><td class="r">'+hvM2(g.va)+' <span class="m">'+hvPc(g.va,t)+'</span></td><td class="r">'+hvM2(g.at)+' <span class="m">'+hvPc(g.at,t)+'</span></td></tr>'}
const hvCab=p=>'<tr><th>'+p+'</th><th class="r">Docs</th><th class="r">Vendas</th><th class="r">Ticket médio</th><th class="r">Varejo</th><th class="r">Atacado</th></tr>';
function R_hv(){const H=hvDados();if(!H.dias.length)return '<div class="card"><b>Histórico de vendas</b><p class="m">Sem dados do Eticadata nesta versão.</p></div>';
 const anos=[...new Set(H.dias.map(r=>r[0].slice(0,4)))].sort(),vends=[...new Set(H.dias.map(r=>r[2]))].sort();
 const rows=hvFiltrar({de:hvS.ano?hvS.ano+'-01-01':'',ate:hvS.ano?hvS.ano+'-12-31':'',vendedor:hvS.vend});
 const T=[...hvAgg(rows,()=>'t').values()][0]||{n:0,v:0,va:0,at:0,nd:0},tt=T.va+T.at+T.nd;
 const porPer=hvAgg(rows,r=>hvS.ano?r[0].slice(0,7):r[0].slice(0,4)),porV=hvAgg(rows,r=>r[2]);
 const vSel=hvS.vend?vends.find(x=>x===hvS.vend):'',arts=(vSel&&H.artigosVend[vSel]?H.artigosVend[vSel].map(a=>[a[0],a[1],a[2],a[3],null]):H.artigos).filter(a=>!hvS.q||(a[0]+' '+a[1]).toLowerCase().includes(hvS.q.toLowerCase())).slice(0,40);
 const zm=new Map();H.zonas.filter(z=>!hvS.vend||z[1]===hvS.vend).forEach(z=>{const g=zm.get(z[2])||[0,0,0];g[0]+=z[3];g[1]+=z[4];g[2]+=z[5];zm.set(z[2],g)});
 const zt=[...zm.values()].reduce((s,g)=>s+g[0]+g[1]+g[2],0);
 return '<div class="card"><b>📊 Histórico de vendas — Eticadata ERP19 + ERP22</b><p class="m">'+esc(H.fonte||'')+'. Dados até '+fdt(H.dias[H.dias.length-1][0])+' (atualizado em '+fdt(H.gerado)+'). Varejo = Cliente, Cliente VIP, Pastor, Missionários · Atacado = Livrarias, Igrejas, Revendedores, Pastor Revendedor, Empresas/Instituições.</p>'+
  '<div class="row"><label class="m">Ano <select data-hv="ano"><option value="">Todos (2016–hoje)</option>'+anos.map(a=>'<option'+(a===hvS.ano?' selected':'')+'>'+a+'</option>').join('')+'</select></label><label class="m">Vendedor <select data-hv="vend"><option value="">Todos</option>'+vends.map(v=>'<option'+(v===hvS.vend?' selected':'')+'>'+esc(v)+'</option>').join('')+'</select></label><button data-lb2="hvx">⬇ Excel</button><button class="p" data-lb2="hvf">💾 Lançar entradas no Financeiro</button><button data-lb2="hvr" title="Retirar do Financeiro as entradas lançadas a partir do histórico">↩ Retirar</button></div>'+
  '<div class="k">'+kc('Vendas',hvM2(T.v),'pos')+kc('Documentos de venda',T.n.toLocaleString('pt-PT'))+kc('Ticket médio',T.n?hvM2(T.v/T.n):'—')+kc('Varejo',hvPc(T.va,tt))+kc('Atacado',hvPc(T.at,tt))+kc('Sem tipo',hvPc(T.nd,tt))+'</div></div>'+
  '<div class="card"><b>'+(hvS.ano?'Por mês de '+hvS.ano:'Por ano')+'</b><div class="tw"><table>'+hvCab(hvS.ano?'Mês':'Ano')+[...porPer.entries()].sort().map(([k,g])=>hvLinha(k,g)).join('')+'</table></div></div>'+
  '<div class="card"><b>Por vendedor'+(hvS.ano?' em '+hvS.ano:'')+'</b><div class="tw"><table>'+hvCab('Vendedor')+[...porV.entries()].sort((a,b)=>b[1].v-a[1].v).map(([k,g])=>hvLinha(k,g)).join('')+'</table></div></div>'+
  '<div class="card"><b>Por província'+(hvS.vend?' — '+esc(hvS.vend):'')+'</b><p class="m">Período completo de cada sistema (o relatório por zona não tem datas).</p><div class="tw"><table><tr><th>Província</th><th class="r">Varejo</th><th class="r">Atacado</th><th class="r">Total</th><th class="r">%</th></tr>'+[...zm.entries()].sort((a,b)=>(b[1][0]+b[1][1]+b[1][2])-(a[1][0]+a[1][1]+a[1][2])).map(([k,g])=>'<tr><td>'+esc(k)+'</td><td class="r">'+hvM2(g[0])+'</td><td class="r">'+hvM2(g[1])+'</td><td class="r">'+hvM2(g[0]+g[1]+g[2])+'</td><td class="r">'+hvPc(g[0]+g[1]+g[2],zt)+'</td></tr>').join('')+'</table></div></div>'+
  '<div class="card"><b>Artigos mais vendidos'+(vSel?' por '+esc(vSel):'')+'</b> <span class="m">(2016–hoje)</span><div class="row"><input id="hvQ" placeholder="Pesquisar artigo ou código" value="'+esc(hvS.q)+'" style="flex:1"><button data-lb2="hvq">🔎</button></div><div class="tw"><table><tr><th>Código</th><th>Artigo</th><th class="r">Qtd.</th><th class="r">Valor</th></tr>'+arts.map(a=>'<tr><td>'+esc(a[0])+'</td><td>'+esc(a[1])+'</td><td class="r">'+(+a[2]).toLocaleString('pt-PT')+'</td><td class="r">'+hvM2(a[3])+'</td></tr>').join('')+'</table></div></div>'}
VIEW.hv=R_hv;TABS.push(['hv','📊 Histórico de vendas']);
document.addEventListener('change',e=>{const t=e.target;if(!t.dataset||!t.dataset.hv)return;hvS[t.dataset.hv]=t.value;render()});
document.addEventListener('keydown',e=>{if(e.target&&e.target.id==='hvQ'&&e.key==='Enter'){hvS.q=e.target.value;render()}});
document.addEventListener('click',e=>{const b=e.target.closest('#liv [data-lb2]');if(!b)return;
 if(b.dataset.lb2==='hvq'){hvS.q=($l('hvQ')||{}).value||'';render()}
 if(b.dataset.lb2==='hvx'){const H=hvDados();xls('CPAD_historico_vendas.xlsx',H.dias.map(r=>({Data:r[0],Sistema:r[1],Vendedor:r[2],Documentos:r[3],Vendas:r[4],Varejo:r[5],Atacado:r[6],Sem_tipo:r[7]})),'Vendas por dia')}});

// ---- Roger: assistente que consulta os dados (só leitura) através do Claude
const JV_TOOLS=[
 {name:'vendas',description:'Vendas do histórico Eticadata (2016–hoje): documentos de venda, valor sem IVA, ticket médio, varejo e atacado. Filtra por datas (YYYY-MM-DD) e vendedor (parte do nome) e agrupa por total, ano, mes, dia ou vendedor. Devolve no máximo 60 linhas.',
  inputSchema:{type:'object',properties:{de:{type:'string'},ate:{type:'string'},vendedor:{type:'string'},agrupar:{type:'string',enum:['total','ano','mes','dia','vendedor']}}},
  execute(i){const rows=hvFiltrar({de:String(i.de||''),ate:String(i.ate||''),vendedor:String(i.vendedor||'')}),a=String(i.agrupar||'total');
   const m=hvAgg(rows,r=>a==='ano'?r[0].slice(0,4):a==='mes'?r[0].slice(0,7):a==='dia'?r[0]:a==='vendedor'?r[2]:'total');
   const out=[...m.entries()].sort((x,y)=>a==='vendedor'?y[1].v-x[1].v:x[0]<y[0]?-1:1).slice(-60).map(([k,g])=>({chave:k,documentos:g.n,vendas:Math.round(g.v*100)/100,ticket_medio:g.n?Math.round(g.v/g.n*100)/100:0,varejo:Math.round(g.va),atacado:Math.round(g.at),sem_tipo:Math.round(g.nd)}));
   return {linhas:out,nota:'Valores sem IVA, incluem faturas (Análise de Vendas do Eticadata).'}}},
 {name:'vendedores',description:'Lista dos vendedores do histórico com primeiro e último dia de venda e total vendido.',
  execute(){const m=new Map();hvDados().dias.forEach(r=>{const g=m.get(r[2])||{de:r[0],ate:r[0],vendas:0};g.ate=r[0];g.vendas+=r[4];m.set(r[2],g)});return [...m.entries()].map(([k,g])=>({vendedor:k,de:g.de,ate:g.ate,vendas:Math.round(g.vendas)}))}},
 {name:'zonas',description:'Vendas por província (varejo, atacado, sem tipo), opcionalmente de um vendedor e de um sistema (ERP19 ou ERP22). Sem datas: cobre o período completo de cada sistema.',
  inputSchema:{type:'object',properties:{vendedor:{type:'string'},sistema:{type:'string'}}},
  execute(i){const v=String(i.vendedor||'').toLowerCase(),s=String(i.sistema||'').toUpperCase(),m=new Map();hvDados().zonas.filter(z=>(!v||z[1].toLowerCase().includes(v))&&(!s||z[0]===s)).forEach(z=>{const g=m.get(z[2])||{varejo:0,atacado:0,sem_tipo:0};g.varejo+=z[3];g.atacado+=z[4];g.sem_tipo+=z[5];m.set(z[2],g)});return [...m.entries()].map(([k,g])=>({provincia:k,varejo:Math.round(g.varejo),atacado:Math.round(g.atacado),sem_tipo:Math.round(g.sem_tipo)}))}},
 {name:'tipos_cliente',description:'Vendas por tipo de entidade (Cliente, Cliente VIP, Igreja, Livraria...) com o canal varejo/atacado, por sistema.',
  execute(){return hvDados().tipos.map(t=>({sistema:t[0],tipo:t[1],canal:t[2],valor:Math.round(t[3])}))}},
 {name:'artigos',description:'Artigos mais vendidos (2016–hoje): código, título, quantidade, valor. Opcional: vendedor (nome completo ou parte) e pesquisa no título/código. Máximo 30.',
  inputSchema:{type:'object',properties:{vendedor:{type:'string'},pesquisa:{type:'string'},n:{type:'number'}}},
  execute(i){const H=hvDados(),v=String(i.vendedor||'').toLowerCase(),q=String(i.pesquisa||'').toLowerCase(),n=Math.min(30,+i.n||15);
   let L=H.artigos;if(v){const k=Object.keys(H.artigosVend).find(x=>x.toLowerCase().includes(v));L=k?H.artigosVend[k]:[]}
   return L.filter(a=>!q||(a[0]+' '+a[1]).toLowerCase().includes(q)).slice(0,n).map(a=>({codigo:a[0],titulo:a[1],quantidade:a[2],valor:Math.round(a[3])}))}},
 {name:'stock',description:'Produtos e stock atuais do ERP da CPAD: pesquisa por título, código ou ISBN. Devolve até 20 com preço e stock.',
  inputSchema:{type:'object',properties:{pesquisa:{type:'string'}},required:['pesquisa']},
  async execute(i){try{await init()}catch(e){}const q=String(i.pesquisa||'').toLowerCase();return A.filter(a=>(String(a.n)+' '+a.c+' '+(a.isbn||'')).toLowerCase().includes(q)).slice(0,20).map(a=>({codigo:a.c,titulo:a.n,preco:a.p,stock:a.s}))}},
 {name:'financeiro_mes',description:'Entradas e saídas registadas no Financeiro do ERP num mês (YYYY-MM), por categoria, e o saldo.',
  inputSchema:{type:'object',properties:{mes:{type:'string'}},required:['mes']},
  async execute(i){const F=window.FIN?await FIN.get():{mov:[]},m=String(i.mes||'').slice(0,7),E={},S={};let te=0,ts=0;(F.mov||[]).filter(x=>String(x.data).slice(0,7)===m).forEach(x=>{if(x.tipo==='E'){E[x.cat]=(E[x.cat]||0)+x.valor;te+=x.valor}else if(x.tipo==='S'){S[x.cat]=(S[x.cat]||0)+x.valor;ts+=x.valor}});return {mes:m,entradas:E,saidas:S,total_entradas:Math.round(te),total_saidas:Math.round(ts),saldo:Math.round(te-ts)}}}];
const JV_REGRAS=()=>'És o Roger, assistente interno da CPAD Moçambique (livraria e editora cristã em Maputo, Av. Eduardo Mondlane 1178). Respondes em português de Moçambique, com cordialidade. Usa SEMPRE as ferramentas para obter números e nunca inventes valores; se uma ferramenta não tiver o dado, diz isso. Indica a origem: «Histórico Eticadata» (valores sem IVA, incluem faturas) ou «ERP da CPAD» (stock, financeiro). Valores em meticais (MT) com separador de milhares. Varejo = Cliente, Cliente VIP, Pastor, Missionários; Atacado = Livrarias, Igrejas, Revendedores, Pastor Revendedor, Empresas/Instituições. Só fazes consultas: não alteras dados. Respostas curtas; usa uma tabela em Markdown quando comparares várias linhas. Hoje é '+hoje()+'.';
let jvT=[],jvCtl=null,jvSample;
(async()=>{try{jvSample=window.claude?await claude.use('sample'):null}catch(e){jvSample=null}if(!jvSample)return;
 const st=document.createElement('style');st.textContent='#jvB{position:fixed;right:16px;bottom:16px;z-index:60;border-radius:99px;padding:12px 18px;background:var(--gold,#C9A85C);color:#0B1F3A;font-weight:700;border:0;box-shadow:0 4px 18px #0006}#jvP{position:fixed;right:16px;bottom:72px;z-index:61;width:min(440px,calc(100vw - 32px));height:min(620px,calc(100vh - 110px));background:var(--card);border:1px solid var(--bd);border-radius:14px;display:none;flex-direction:column;box-shadow:0 8px 40px #0008}#jvP.on{display:flex}#jvL{flex:1;overflow:auto;padding:12px;display:flex;flex-direction:column;gap:8px}#jvL .u{align-self:flex-end;background:var(--in);border:1px solid var(--bd);border-radius:12px;padding:8px 12px;max-width:85%}#jvL .a{align-self:flex-start;white-space:pre-wrap;max-width:95%;line-height:1.45}#jvP form{display:flex;gap:6px;padding:10px;border-top:1px solid var(--bd)}#jvP textarea{flex:1;min-height:44px;max-height:120px}';
 document.head.appendChild(st);
 const b=document.createElement('button');b.id='jvB';b.textContent='🤖 Roger';document.body.appendChild(b);
 const p=document.createElement('div');p.id='jvP';p.innerHTML='<div class="row" style="padding:10px 12px;border-bottom:1px solid var(--bd);justify-content:space-between"><b>🤖 Roger — assistente CPAD</b><span><button type="button" id="jvN" title="Nova conversa">🗑</button> <button type="button" id="jvX">✕</button></span></div><div id="jvL"><div class="a m">Paz do Senhor! Pergunte sobre vendas (2016–hoje), vendedores, varejo e atacado, províncias, artigos mais vendidos, stock ou o financeiro do mês. Ex.: «Quanto vendeu o Damião em outubro de 2026?»</div></div><form id="jvF"><textarea id="jvI" placeholder="Escreva a pergunta…"></textarea><button class="p" id="jvS">Enviar</button><button type="button" id="jvStop" hidden>■</button></form>';
 document.body.appendChild(p);
 const L=document.getElementById('jvL'),I=document.getElementById('jvI'),S=document.getElementById('jvS'),Stop=document.getElementById('jvStop');
 const add=(c,t)=>{const d=document.createElement('div');d.className=c;d.textContent=t;L.appendChild(d);L.scrollTop=L.scrollHeight;return d};
 b.onclick=()=>{p.classList.toggle('on');if(p.classList.contains('on'))I.focus()};
 document.getElementById('jvX').onclick=()=>p.classList.remove('on');
 document.getElementById('jvN').onclick=()=>{jvCtl&&jvCtl.abort();jvT=[];L.innerHTML='';add('a m','Nova conversa. O que quer saber?')};
 Stop.onclick=()=>jvCtl&&jvCtl.abort();
 I.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();document.getElementById('jvF').requestSubmit()}});
 document.getElementById('jvF').onsubmit=async e=>{e.preventDefault();const q=I.value.trim();if(!q||jvCtl)return;I.value='';add('u',q);jvT.push({role:'user',content:q});
  const out=add('a','A pensar…');S.disabled=true;Stop.hidden=false;jvCtl=new AbortController();
  try{const turns=[{role:'user',content:JV_REGRAS()},...jvT.slice(-12)];
   const r=await jvSample(turns,{tools:JV_TOOLS,signal:jvCtl.signal,onText:({text})=>{out.textContent=text;L.scrollTop=L.scrollHeight}});
   out.textContent=r.text;jvT.push({role:'assistant',content:r.text});if(r.truncated)add('a m','(resposta cortada — peça menos de cada vez)')}
  catch(x){if(x&&x.text)out.textContent=x.text;else out.remove();
   const msg={not_granted:'O Roger precisa da sua autorização para usar o Claude.',sampling_disabled:'O Claude não está disponível nesta conta.',rate_limited:'Muitos pedidos seguidos — tente daqui a pouco.',tools_unavailable:'Esta vista não permite que o Roger consulte os dados.',cancelled:''}[x&&x.code];
   if(msg!=='')add('a m',msg||'Não foi possível responder agora. Tente de novo.');jvT.pop()}
  finally{jvCtl=null;S.disabled=false;Stop.hidden=true;I.focus()}}})();
// ---- Lançar o histórico como entradas no Financeiro (todos os anos; salta dias que já têm vendas lançadas)
const HV_FP='Histórico Eticadata';
const HV_CAT={b:'Vendas — balcão',r:'Vendas — revendedores',i:'Vendas — igrejas e instituições'};
let _hvFP=null;function hvFP(){if(_hvFP)return _hvFP;_hvFP={};(hvDados().fp||[]).forEach(([d,k,f,v])=>{(_hvFP[d]||(_hvFP[d]=[])).push([k,f,v])});
 Object.values(_hvFP).forEach(a=>{const t={};a.forEach(([k,f,v])=>{t[k]=(t[k]||0)+v});a.forEach(x=>{if(t[x[0]]<0)x[2]=0})});return _hvFP}
function hvEntradas(){const dias={};hvDados().dias.forEach(r=>{const g=dias[r[0]]||(dias[r[0]]={b:0,r:0,i:0,n:0});g.b+=r[5]+r[7];g.r+=(r[9]||0);g.i+=(r[8]||0)+(r[10]||0);g.n+=r[3]});return dias}
async function hvLancarFinanceiro(){if(!window.FIN){toast('Financeiro indisponível.',1);return}
 const F=await FIN.get(),ja=new Set((F.mov||[]).filter(m=>m.tipo==='E'&&String(m.cat).indexOf('Vendas')===0&&String(m.id).indexOf('hist-')!==0).map(m=>m.data));
 const anosOreate=new Set((F.mov||[]).filter(m=>String(m.nota||'').indexOf('Oreate')===0).map(m=>String(m.data).slice(0,4)));
 const dias=hvEntradas(),novas=[];let saltados=0,tot=0,comFP=0;
 for(const [d,g] of Object.entries(dias).sort()){if(ja.has(d)||anosOreate.has(d.slice(0,4))){saltados++;continue}
  let b=g.b,r=g.r,i=g.i;if(r<0){b+=r;r=0}if(i<0){b+=i;i=0}
  const fpd=hvFP()[d];
  if(fpd){fpd.forEach(([k,forma,v],j)=>{v=Math.round(v*100)/100;if(v>0){novas.push({id:'hist-'+d+'-'+k+'-'+j,data:d,tipo:'E',cat:HV_CAT[k],parte:'Eticadata — Diário de Vendas',fp:forma,valor:v,nota:'Histórico Eticadata · sem IVA · forma pelo Diário de Vendas (cruzado por documento)'});tot+=v;comFP++}})}
  else [['b','Vendas — balcão',b],['r','Vendas — revendedores',r],['i','Vendas — igrejas e instituições',i]].forEach(([k,cat,v])=>{v=Math.round(v*100)/100;if(v>0){novas.push({id:'hist-'+d+'-'+k,data:d,tipo:'E',cat,parte:'Eticadata — Análise de Vendas',fp:HV_FP,valor:v,nota:'Histórico Eticadata · sem IVA · '+g.n+' docs · forma de pagamento por confirmar'});tot+=v}})}
 const antigos=(F.mov||[]).filter(m=>String(m.id).indexOf('hist-')===0).length;
 if(!confirm('Lançar '+novas.length.toLocaleString('pt-PT')+' entradas de vendas no Financeiro ('+Object.keys(dias).length.toLocaleString('pt-PT')+' dias de 2016 a hoje, '+hvM2(tot)+').\n\n'+saltados+' dias ficam de fora porque já têm vendas lançadas (os anos importados do Oreate, como 2025, ficam inteiros como estão).'+(antigos?'\n'+antigos+' lançamentos anteriores do histórico serão substituídos.':'')+'\n\n'+comFP.toLocaleString('pt-PT')+' entradas levam a forma de pagamento real do Diário de Vendas (ERP19 e ERP22, cruzado por documento): Dinheiro, Cartão / POS, Transferência, Cheque, misto ou a crédito (faturas). O que não aparece no Diário fica «Por confirmar».\n\nAs entradas aparecem em Vendas, Faturamento, Metas e relatórios. Por serem histórico (sem as despesas e depósitos desses anos), não mexem no saldo de caixa e bancos.'))return;
 F.mov=(F.mov||[]).filter(m=>String(m.id).indexOf('hist-')!==0);await FIN.addMany(novas);
 toast(novas.length.toLocaleString('pt-PT')+' entradas lançadas no Financeiro.');render()}
async function hvRetirarFinanceiro(){if(!window.FIN)return;const F=await FIN.get(),n=(F.mov||[]).filter(m=>String(m.id).indexOf('hist-')===0).length;
 if(!n){toast('Não há entradas do histórico no Financeiro.');return}if(!confirm('Retirar as '+n+' entradas do histórico do Financeiro?'))return;
 F.mov=F.mov.filter(m=>String(m.id).indexOf('hist-')!==0);await FIN.addMany([]);toast('Entradas do histórico retiradas.');render()}
document.addEventListener('click',e=>{const b=e.target.closest('#liv [data-lb2]');if(!b)return;if(b.dataset.lb2==='hvf')hvLancarFinanceiro();if(b.dataset.lb2==='hvr')hvRetirarFinanceiro()});
