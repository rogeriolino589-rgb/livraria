import json
# faturas mensais vistas nos e-mails da Scanaudit (assunto/corpo); None = e-mail do mês sem nº de fatura
FAT={'2022-07':972,'2022-08':978,'2022-09':984,'2022-10':990,'2022-11':997,'2022-12':1004,
'2023-01':1011,'2023-02':1019,'2023-03':1027,'2023-04':1034,'2023-05':1044,'2023-06':1054,'2023-07':1064,'2023-08':1072,'2023-09':1081,'2023-10':1088,'2023-11':1096,'2023-12':1104,
'2024-01':1112,'2024-02':1121,'2024-03':1131,'2024-04':1141,'2024-05':1150,'2024-06':1160,'2024-07':1170,'2024-08':1179,'2024-09':1188,'2024-10':1197,'2024-11':1206,'2024-12':1215,
'2025-04':1251,'2025-05':1260,'2025-06':1269,'2025-07':1278,'2025-08':1286,'2025-09':1295,'2025-10':1302,'2025-11':1310,
'2026-01':1324,'2026-02':1333,'2026-03':1341,'2026-04':1348,'2026-06':1365,'2026-07':None,'2026-08':1380,'2026-09':1387,'2026-10':1394}
fee=lambda m:33640.0 if m>='2026' else 31320.0
d=json.load(open('fin_brd_swf.json'))
pays=sorted([(x['data'][:7],x['valor'],x['id']) for x in d if x['id'].startswith(('brd-','scan-')) and 'scanaudit' in x.get('parte','').lower()])
def mi(m): y,mm=map(int,m.split('-')); return y*12+mm
for m in ('2025-01','2025-02','2025-03','2025-12','2026-05'): FAT.setdefault(m,'?')
inv=sorted(FAT); matched={'2026-10':'scan-1394-2026-10-a'}
for pm,v,i in pays:
    if i=='brd-052958391' or i.startswith('scan-'): continue   # consultoria/vistos, não é a avença mensal
    n=max(1,int(v/fee(pm)+0.05))
    for _ in range(n):
        c=None
        for lag in (1,0,2,3,4,5,6,-1):
            k=[m for m in inv if m not in matched and mi(pm)-mi(m)==lag]
            if k: c=k[0]; break
        if c: matched[c]=i
        else: print('pagamento sem fatura',pm,v,i)
falta=[m for m in inv if m not in matched and FAT[m]!='?']
print('faturas',len(inv),'pagas em borderô',len(matched),'sem borderô',len(falta))
for m in inv: print(m,FAT[m],matched.get(m,'— SEM BORDERÔ'))
json.dump({m:FAT[m] for m in falta},open('fat_scan_falta.json','w'))
