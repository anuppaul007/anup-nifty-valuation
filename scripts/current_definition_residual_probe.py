#!/usr/bin/env python3
"""Probe the two remaining hypotheses for Sep-2023 anchor residuals."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import current_definition_anchor_validation_v3 as v3

a=v3.a
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_residual_probe.json'
SPECIAL=['HDFCLIFE','LTIM','NESTLEIND','SBILIFE','TATAMOTORS']
CAP=['AXISBANK','HCLTECH','HDFCBANK','ICICIBANK','KOTAKBANK','SBIN']


def dated(sym,period):
    base={'index':'equities','symbol':sym,'period':period,'from_date':'01-01-2022','to_date':'29-09-2023'}
    try:
        d=a.get_json('https://www.nseindia.com/api/corporates-financial-results',base)
        rows=d if isinstance(d,list) else d.get('data',[]) if isinstance(d,dict) else []
        return {'status':'ok','count':len(rows),'keys':sorted(rows[0].keys()) if rows else [],'rows':[{k:r.get(k) for k in ('symbol','companyName','fromDate','toDate','filingDate','broadCastDate','consolidated','cumulative','period','financialYear','relatingTo','xbrl')} for r in rows[:30]]}
    except Exception as e:return {'status':'unavailable','error':f'{type(e).__name__}: {e}'}


def capish(sym):
    try:
        rows=a.financial_rows(sym,'Quarterly')
        row=a.choose_basis(rows)
        if not row:return {'status':'no_eligible'}
        fs=a.facts(a.xbrl_root(row['xbrl']));hits=[]
        for f in fs:
            n=f['name'].lower()
            if any(k in n for k in ('capital','facevalue','numberofshare','paidup','equityshare')):
                hits.append({'name':f['name'],'value':f['value'],'context':f['context'],'period':f['period']})
        return {'status':'ok','row':{k:row.get(k) for k in ('fromDate','toDate','filingDate','consolidated','cumulative','xbrl')},'hits':hits[:100]}
    except Exception as e:return {'status':'unavailable','error':f'{type(e).__name__}: {e}'}


def main():
    out={'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'research_only':True,'live_model_changed':False,
         'dated':{s:{p:dated(s,p) for p in ('Quarterly','Half Yearly','Annual')} for s in SPECIAL},
         'capital':{s:capish(s) for s in CAP}}
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps({'dated':{s:{p:v[p].get('count') for p in v} for s,v in out['dated'].items()},'capital':{s:v.get('status') for s,v in out['capital'].items()}},indent=2))

if __name__=='__main__':main()
