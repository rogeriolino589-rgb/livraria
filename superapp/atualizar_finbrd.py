# Uso: atualizar_finbrd.py <html_publicado> <fin_brd_swf.json> <saida.html>
# Troca só o bloco <script id="finBrd"> do HTML publicado, preservando o resto (alterações de outras sessões).
import sys,re
s=open(sys.argv[1],encoding='utf-8').read()
fb=open(sys.argv[2],encoding='utf-8').read().replace('</','<\\/')
pat=re.compile(r'(<script id="finBrd" type="application/json">)(.*?)(</script>)',re.S)
assert len(pat.findall(s))==1
s=pat.sub(lambda m:m.group(1)+fb+m.group(3),s)
open(sys.argv[3],'w',encoding='utf-8').write(s);print('ok',len(s))
