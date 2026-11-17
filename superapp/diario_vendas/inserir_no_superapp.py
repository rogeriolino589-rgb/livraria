# Uso: inserir_dv.py <html_base> <dv_dados.json> <modulo_dv.js> <saida.html>  — idempotente
import sys,re
s=open(sys.argv[1],encoding='utf-8').read();dados=open(sys.argv[2],encoding='utf-8').read().replace('</','<\\/');mod=open(sys.argv[3],encoding='utf-8').read().rstrip('\n')
s=re.sub(r'<script id="dvData" type="application/json">.*?</script>\n?','',s,flags=re.S)
s=re.sub(r'\n?/\* ---------- Diário de vendas 2016–2022.*?VIEW\.dv=R_dv;','',s,flags=re.S)
def troca(a,b):
  global s
  assert s.count(a)==1,('não único',a[:60],s.count(a));s=s.replace(a,b)
troca('VIEW.cm=R_cm;','VIEW.cm=R_cm;\n'+mod)
if "['dv','📒 Diário de vendas']" not in s: troca("['cm','📊 Comparativos'],","['cm','📊 Comparativos'],['dv','📒 Diário de vendas'],")
if "'liv','dv']" not in s: troca("['📊','Histórico de vendas (Eticadata)','liv','hv'],","['📊','Histórico de vendas (Eticadata)','liv','hv'],['📒','Diário de vendas 2016–2022','liv','dv'],")
troca('<script id="finBrd" type="application/json">','<script id="dvData" type="application/json">'+dados+'</script>\n<script id="finBrd" type="application/json">')
open(sys.argv[4],'w',encoding='utf-8').write(s);print('ok',len(s))
