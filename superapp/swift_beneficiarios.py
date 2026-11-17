import json,re,unicodedata
B='/home/user/livraria/relatorios/saidas_admin/swifts.json'
L=json.load(open(B))
def sa(s): return unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().upper()
REG=[(r'CARGO.?MAR','Cargomar Agência de Cargas','Transporte (frete)'),(r'NOVAIRMOV','Novairmov Transitários','Transporte (frete)'),
 (r'CASA PUB|ASSEMBLEIAS DE DEUS','CPAD Brasil (Casa Publicadora das Assembleias de Deus)','CPAD Brasil'),
 (r'MUNDO( CRIST|$)','Editora Mundo Cristão','Outras editoras'),(r'BELLO COM','Bello Comércio e Publicações','Outras editoras'),
 (r'B[RV] FIL','BV Films Editora','Outras editoras'),(r'VIDA MELHO','Vida Melhor Editora','Outras editoras'),
 (r'VIDA NOVA|SOCIEDADE RELIGIOSA ED VIDA$','Sociedade Religiosa Edições Vida Nova','Outras editoras'),
 (r'^(ED\.? VIDA|EDITORA? V[IO]DA|EDITOR VIDA)','Editora Vida','Outras editoras'),
 (r'BELLA A','Editora e Distribuidora Bella Arte','Outras editoras'),(r'HAGNOS','Editora Hagnos','Outras editoras'),
 (r'LUZ E VIDA','Editora Luz e Vida','Outras editoras'),(r'FOLKART','Folkart Importação e Exportação','Outras editoras'),
 (r'GEO ?GRAFICA','Geográfica Editora','Outras editoras'),(r'GILGAL','Gilgal Gospel','Outras editoras'),
 (r'JOLK','Jolk Art Importação e Exportação','Outras editoras'),(r'PAO DIARIO','Ministérios Pão Diário','Outras editoras'),
 (r'TRINITARIANA','Sociedade Bíblica Trinitariana do Brasil','Outras editoras'),(r'SERGIO GALHA','Sérgio Galha Júnior ME','Outras editoras'),
 (r'ALWAYS CAP','Always Cap Comércio Imp. Exp.','Outras editoras'),(r'SONY','Sony Music Entertainment Africa','Outras editoras'),
 (r'NISSAN','Produkta Nissan','Compra de viatura'),(r'AC CONTAB','AC Contabilidade Gestão SA','Outros'),(r'MONICA','Mónica Maria Guerreiro Soares Monteiro','Outros')]
FAT={'OPM20251103058':('009/25','1.ª parcela'),'OPM20260202257':('009/25','2.ª parcela'),'OPM20260304299':('009/25','liquidação (3.ª)'),
     'OPM20260500560':('021/2025','1.ª parcela'),'OPM20260700135':('021/2025','2.ª parcela'),'OPM20260704732':('021/2025','saldo final (3.ª)')}
sem=[]
for x in L:
    b=sa(x['benef'])
    for p,n,g in REG:
        if re.search(p,b): x['benef_nome']=n; x['benef_grupo']=g; break
    else: sem.append(x['benef'])
    f=FAT.get(x['ref']); x['fatura']=f[0] if f else ''; x['parcela']=f[1] if f else ''
json.dump(L,open(B,'w'),ensure_ascii=False,indent=1)
import collections
print('sem regra:',sem); print(collections.Counter(x['benef_nome'] for x in L).most_common())
print('com fatura',sum(1 for x in L if x['fatura']))
