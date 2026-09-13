#!/usr/bin/env python3
"""Probe Nifty Indices' official historical-data endpoint for pre-2011 G-sec values."""
from __future__ import annotations
from pathlib import Path
import ast,json,requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'trend_debt_archive_probe.json'
URL='https://www.niftyindices.com/Backpage.aspx/getHistoricaldatatabletoString'
HEAD={
 'Content-Type':'application/json; charset=UTF-8','Accept':'application/json, text/javascript, */*; q=0.01',
 'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
 'X-Requested-With':'XMLHttpRequest','Origin':'https://www.niftyindices.com','Referer':'https://www.niftyindices.com/reports/historical-data'
}
NAMES=['Nifty 10 yr Benchmark G-Sec','NIFTY 10 YR BENCHMARK G-SEC','Nifty 10 Yr Benchmark G-sec']

def decode(text):
    x=text.lstrip('\ufeff').strip()
    try:x=json.loads(x)
    except Exception:
        try:x=ast.literal_eval(x)
        except Exception:return None
    if isinstance(x,dict) and 'd' in x:x=x['d']
    if isinstance(x,str):
        try:x=json.loads(x)
        except Exception:
            try:x=ast.literal_eval(x)
            except Exception:return None
    return x

def main():
    s=requests.Session()
    seed=None
    try:
        z=s.get('https://www.niftyindices.com/reports/historical-data',headers=HEAD,timeout=20);seed={'status':z.status_code,'content_type':z.headers.get('content-type')}
    except Exception as e:seed={'error':f'{type(e).__name__}: {e}'}
    attempts=[]
    for name in NAMES:
        cinfo=f"{{'name':'{name}','startDate':'01-Jan-2001','endDate':'31-Dec-2010','indexName':'{name}'}}"
        try:
            r=s.post(URL,json={'cinfo':cinfo},headers=HEAD,timeout=60);data=decode(r.text);rows=data if isinstance(data,list) else []
            attempts.append({'name':name,'http_status':r.status_code,'content_type':r.headers.get('content-type'),'raw_prefix':r.text[:500],'decoded_type':type(data).__name__ if data is not None else None,'count':len(rows),'first_row':rows[0] if rows else None,'last_row':rows[-1] if rows else None,'keys':sorted(rows[0].keys()) if rows and isinstance(rows[0],dict) else []})
        except Exception as e:attempts.append({'name':name,'error':f'{type(e).__name__}: {e}'})
    out={'research_only':True,'endpoint':URL,'period':['2001-01-01','2010-12-31'],'seed':seed,'attempts':attempts,'substitution_allowed':False}
    OUT.write_text(json.dumps(out,indent=2,default=str),encoding='utf-8');print(json.dumps(out,indent=2,default=str))

if __name__=='__main__':main()
