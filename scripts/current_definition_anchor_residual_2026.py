#!/usr/bin/env python3
"""Targeted schema diagnostic for remaining Aug-2026 anchor edge cases."""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import json,time
import current_definition_integrated_anchor as a
import current_definition_integrated_coverage as cov

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_anchor_residual_2026.json'
CASES=['AXISBANK','HDFCBANK','ICICIBANK','KOTAKBANK','SBIN','INDIGO','NESTLEIND','HDFCLIFE','SBILIFE']
KEYS=('equity','capital','reserve','surplus','networth','networth','shareholder','profit','loss','facevalue','earning')

def inspect(s,row):
    listings,issuer=a.listings_for(s,row);result={'issuer':issuer,'quarters':{}}
    for q in ('31-MAR-2026','30-JUN-2026'):
        sel,basis=a.choose_quarter(listings,q)
        if not sel:
            result['quarters'][q]={'error':'missing'};continue
        try:
            fs=a.numeric_facts(a.fetch_xml(s,sel['xbrl']))
            rel=[]
            for f in fs:
                if any(k in f['name'].lower() for k in KEYS):rel.append(f)
            result['quarters'][q]={'basis':basis,'xbrl':sel['xbrl'],'facts':rel}
        except Exception as e:result['quarters'][q]={'error':f'{type(e).__name__}: {e}'}
        time.sleep(.6)
    return result

def main():
    s=cov.session();rows,_=cov.weight_rows(s);by={r['symbol']:r for r in rows};out={'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'research_only':True,'live_model_changed':False,'cases':{}}
    for sym in CASES:
        if sym not in by:continue
        try:out['cases'][sym]=inspect(s,by[sym])
        except Exception as e:out['cases'][sym]={'error':f'{type(e).__name__}: {e}'}
        time.sleep(.7)
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:{q:len(vv.get('facts',[])) for q,vv in v.get('quarters',{}).items()} for k,v in out['cases'].items()},indent=2))
if __name__=='__main__':main()
