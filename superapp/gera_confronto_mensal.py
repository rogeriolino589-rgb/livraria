import json,csv,datetime as dt
DEP_ATE='2026-11-14'; DEP_ATE1='2026-11-15'
from collections import defaultdict
S='/tmp/claude-0/-home-user-livraria/295e8822-745d-5b40-9305-329d80bb252f/scratchpad/'
B='/home/user/livraria/relatorios/saidas_admin/'
o=json.load(open(B+'oreate_dados.json'))
ms=[f'{y}-{m:02d}' for y in range(2022,2027) for m in range(1,13) if '2022-06'<=f'{y}-{m:02d}'<='2026-11']
Z=lambda:defaultdict(float)
V=defaultdict(Z)
for r in o['DAILY']:
    m=r['d'][:7]
    if m not in ms: continue
    V[m]['e_ven']+=r['car']+r['pos']+r['transf']; c=r['din']+r['fatdin']+r['cheque']; V[m]['din']+=c
    # regra confirmada: dinheiro, fatura em dinheiro e cheque até 14/10/2026 foram todos depositados no dia seguinte
    if r['d']<=DEP_ATE:
        nx=(dt.date.fromisoformat(r['d'])+dt.timedelta(days=1)).isoformat()[:7]
        if nx in ms: V[nx]['e_dep']+=c
    elif r['d']>DEP_ATE1: V[m]['e_dep']+=r['dep']
# dias que o Oreate ainda não tem: mapas de caixa diários da loja (e-mail «Resumo de vendas diário»)
import os
_ore={r['d'] for r in o['DAILY']}
_EX=B+'vendas_out_nov_2026_emails.json'
if os.path.exists(_EX):
    for r in json.load(open(_EX)):
        if r['d'] in _ore or r['d'][:7] not in ms: continue
        V[r['d'][:7]]['e_ven']+=r['pos']+r['transf']; V[r['d'][:7]]['din']+=r['din']
        if r['d']<=DEP_ATE:
            nx=(dt.date.fromisoformat(r['d'])+dt.timedelta(days=1)).isoformat()[:7]
            if nx in ms: V[nx]['e_dep']+=r['din']
for x in json.load(open(S+'fin_brd_swf.json')):
    m=x['data'][:7]
    if m not in ms: continue
    i=x['id']
    if x['tipo']=='E': V[m]['e_dev']+=x['valor']; continue
    k='s_swf' if i.startswith('swf-') else 's_ore' if i.startswith('ore-sai') else 's_est' if i.startswith('est-') else 's_fol' if i.startswith('fol-') else 's_brd'
    V[m][k]+=x['valor']
for x in json.load(open(S+'cc_oreate.json')):
    m=x['data'][:7]
    if m not in ms or x.get('nofin') or '-ini-' in x['id']: continue
    V[m]['c_'+x['t']]+=x['v']
COLS=[('Mês',None),
 ('ENTRADAS · Vendas cartão/POS/transferência','e_ven'),('ENTRADAS · Depósitos de dinheiro/cheque (D+1)','e_dep'),('ENTRADAS · Devoluções recebidas','e_dev'),('TOTAL ENTRADAS BANCO','E'),
 ('ADMIN · Borderôs administrativos','s_brd'),('ADMIN · Folha Scanaudit (recibos/guias reais, sem borderô)','s_fol'),('ADMIN · Estimativas (sem borderô)','s_est'),('ADMIN · Oreate (rubricas sem borderô)','s_ore'),('SUBTOTAL DESPESAS ADMINISTRATIVAS','ADM'),
 ('IMPORTAÇÕES · SWIFT (compras/fretes/comissões)','s_swf'),
 ('SAÍDA PARA RECARGA DO CARTÃO CORPORATIVO','c_R'),
 ('TOTAL SAÍDAS BANCO','S'),('Resultado do mês (banco)','RES'),('Banco acumulado desde jun/2022','ACC'),
 ('Recebido em dinheiro/cheque (loja)','din'),('Dinheiro da loja por depositar (acumulado)','LOJ'),
 ('CONTROLO CARTÃO · Recarga recebida','c_R'),('CONTROLO CARTÃO · Gastos no cartão','c_G'),('CONTROLO CARTÃO · Levantamentos','c_L'),('CONTROLO CARTÃO · Despesas pagas em dinheiro','c_D'),('CONTROLO CARTÃO · Saldo do cartão','SC'),('CONTROLO CARTÃO · Caixa pequena (dinheiro, transita)','SD')]
rows=[];acc=loj=sc=0;sd=53679.51
for m in ms:
    v=V[m]; v['E']=v['e_ven']+v['e_dep']+v['e_dev']; v['ADM']=v['s_brd']+v['s_fol']+v['s_est']+v['s_ore']
    v['S']=v['ADM']+v['s_swf']+v['c_R']; v['RES']=v['E']-v['S']; acc+=v['RES']; v['ACC']=acc
    loj+=v['din']-v['e_dep']; v['LOJ']=loj; sc+=v['c_R']-v['c_G']-v['c_L']; v['SC']=sc; sd+=v['c_L']-v['c_D']; v['SD']=sd
    rows.append([m]+[round(v[k],2) for _,k in COLS[1:]])
HDR=[c for c,_ in COLS]
json.dump({'hdr':HDR,'rows':rows,'keys':[k for _,k in COLS]},open(S+'confronto.json','w'),ensure_ascii=False)
ix={k:i for i,(_,k) in enumerate(COLS) if k}
for y in range(2022,2027):
    R=[r for r in rows if r[0].startswith(str(y))]; s=lambda k:round(sum(r[ix[k]] for r in R))
    print(y,'ent',s('E'),'admin',s('ADM'),'swift',s('s_swf'),'recarga',s('c_R'),'saídas',s('S'),'res',s('RES'),'acum',round(R[-1][ix['ACC']]),'cartão saldo',round(R[-1][ix['SC']],2),'caixa',round(R[-1][ix['SD']],2))
