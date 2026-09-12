#!/usr/bin/env python3
"""Probe NSE Integrated Filing - Financials coverage for a clean 2025 anchor.

Research-only. Uses the public NSE website endpoint with session seeding and
records only metadata needed to decide whether a full post-standardisation
anchor can be reconstructed. No live model files are touched.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json, time
import requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_integrated_probe.json'
UA={
    'accept':'*/*',
    'accept-language':'en-US,en;q=0.9',
    'user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'sec-fetch-dest':'empty','sec-fetch-mode':'cors','sec-fetch-site':'same-origin'
}
CASES={
    'HDFCBANK':'HDFC Bank Limited',
    'HDFCLIFE':'HDFC Life Insurance Company Limited',
    'TATAMOTORS':'Tata Motors Limited',
    'LTIM':'LTIMindtree Limited',
    'SBILIFE':'SBI Life Insurance Company Limited',
    'NESTLEIND':'Nestle India Limited',
    'ICICIBANK':'ICICI Bank Limited',
}

def session():
    s=requests.Session(); s.headers.update(UA)
    for u in ('https://www.nseindia.com/','https://www.nseindia.com/companies-listing/corporate-integrated-filing'):
        try:s.get(u,timeout=20);time.sleep(.5)
        except Exception:pass
    return s

def fetch(s,symbol,issuer):
    url='https://www.nseindia.com/api/integrated-filing-results'
    params={'index':'equities','symbol':symbol,'issuer':issuer,'period_ended':'all','type':'Integrated Filing- Financials','page':1,'size':50}
    last=None
    for i in range(4):
        try:
            r=s.get(url,params=params,headers={**UA,'referer':'https://www.nseindia.com/companies-listing/corporate-integrated-filing'},timeout=30)
            if r.status_code in (401,403,500):
                try:s.get('https://www.nseindia.com/',timeout=15)
                except Exception:pass
                time.sleep(1.2*(i+1)); continue
            r.raise_for_status(); data=r.json()
            rows=data.get('data',[]) if isinstance(data,dict) else []
            return {'status':'ok','http_status':r.status_code,'totalCount':data.get('totalCount') if isinstance(data,dict) else None,'count':len(rows),'keys':sorted(rows[0].keys()) if rows else [],'rows':rows[:3]}
        except Exception as e:
            last=e; time.sleep(1.2*(i+1))
    return {'status':'unavailable','error':f'{type(last).__name__}: {last}'}

def main():
    s=session(); out={'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'research_only':True,'live_model_changed':False,'cases':{}}
    for sym,issuer in CASES.items():
        out['cases'][sym]=fetch(s,sym,issuer);time.sleep(.8)
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:{'status':v.get('status'),'count':v.get('count'),'totalCount':v.get('totalCount')} for k,v in out['cases'].items()},indent=2))

if __name__=='__main__':main()
