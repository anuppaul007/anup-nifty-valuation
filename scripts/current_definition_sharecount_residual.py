#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json,re,time
import current_definition_integrated_anchor_v4 as v4

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_sharecount_residual.json'
a=v4.a
TARGET={'BAJAJFINSV','BHARTIARTL'}
KEY=re.compile(r'(share|capital|face|eps|earningsper|paidup|equity|profit|loss)',re.I)
QUARTERS=('31-MAR-2026','30-JUN-2026')


def main():
    s=a.cov.session() if hasattr(a,'cov') else None
    if s is None:
        import current_definition_integrated_coverage as cov
        s=cov.session(); rows,_=cov.weight_rows(s)
    else:
        rows,_=a.cov.weight_rows(s)
    cases={}
    for row in rows:
        if row['symbol'] not in TARGET:continue
        listings,issuer=a.listings_for(s,row)
        filings={}
        for q in QUARTERS:
            selected,basis=a.choose_quarter(listings,q)
            if not selected:
                filings[q]={'error':'missing'};continue
            fs=a.numeric_facts(a.fetch_xml(s,selected['xbrl']))
            facts=[f for f in fs if KEY.search(f['name'])]
            filings[q]={'basis':basis,'xbrl':selected['xbrl'],'facts':sorted(facts,key=lambda f:(f['context'],f['name']))}
            time.sleep(.4)
        actions=a.corporate_actions(s,row['symbol'])
        cases[row['symbol']]={
            'security_name':row['security_name'],'price':row['price'],'index_mcap_cr':row['index_mcap_cr'],
            'issuer_used':issuer,'filings':filings,
            'action_face_values':sorted({float(x['faceVal']) for x in actions if str(x.get('faceVal','')).strip() not in ('','None') and float(x['faceVal'])>0}),
            'actions':[{'exDate':x.get('exDate'),'subject':x.get('subject'),'faceVal':x.get('faceVal')} for x in actions]
        }
    OUT.write_text(json.dumps({'research_only':True,'cases':cases,'live_model_changed':False},indent=2),encoding='utf-8')
    print(json.dumps({'cases':{k:{'quarters':{q:len(v.get('facts',[])) for q,v in c['filings'].items()},'action_face_values':c.get('action_face_values')} for k,c in cases.items()}},indent=2))

if __name__=='__main__':main()
