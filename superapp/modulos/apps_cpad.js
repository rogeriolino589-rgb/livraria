// ---- Apps CPAD dentro do superapp (páginas próprias, abertas aqui) e links para documentos
window.abrirAppCPAD=function(sub){
 const B=document.body;B.classList.remove('fin-on','liv-on','lead-mode');
 ['liv','fin'].forEach(i=>{const e=document.getElementById(i);if(e)e.hidden=true});
 let w=document.getElementById('appW');
 if(!w){w=document.createElement('div');w.id='appW';w.innerHTML='<iframe id="appF" title="App CPAD" style="width:100%;height:calc(100vh - 110px);border:1px solid var(--bd);border-radius:12px;background:#fff"></iframe>';document.querySelector('main').prepend(w)}
 const src={leads:'apps/leads-mocambique.html',fin3d:'apps/financeiro-3d.html'}[sub];
 const f=document.getElementById('appF');if(f.getAttribute('src')!==src)f.setAttribute('src',src);
 w.hidden=false;B.classList.add('app-on');
 const h1=document.getElementById('erpH1'),sb=document.getElementById('erpSub');
 if(h1)h1.innerHTML='<span>CPAD</span> '+({leads:'Leads Moçambique',fin3d:'Controlo Financeiro 3D'}[sub]||'App');
 if(sb)sb.textContent='App CPAD dentro do superapp · os dados ficam neste navegador';
 const L=document.getElementById('erpLoad');if(L)L.remove();
 document.querySelectorAll('#erpnav .ni').forEach(b=>b.classList.toggle('act',b.dataset.m==='app'&&b.dataset.s===sub));
 B.classList.remove('nav-open')};
