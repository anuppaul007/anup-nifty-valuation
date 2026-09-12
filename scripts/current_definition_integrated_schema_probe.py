#!/usr/bin/env python3
"""Inspect relevant XBRL facts across IndAS, banking and life-insurance integrated filings."""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import json,time,xml.etree.ElementTree as ET
import requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_integrated_schema_probe.json'
UA={'accept':'*/*','user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
CASES={'RELIANCE':'Reliance Industries Ltd.','HDFCBANK':'HDFC Bank Ltd.','HDFCLIFE':'HDFC Life Insurance Company Ltd.','SBILIFE':'SBI Life Insurance Company Ltd.'}

def local(tag):return tag.split('}')[-1].split(':')[-1]
def sess():
    s=requests.Session();s.headers.update(UA)
    try:s.get('https://www.nseindia.com/',timeout=20)
    except Exception:pass
    return s

def listing(s,sym,issuer):
    p={'index':'equities','symbol':sym,'issuer':issuer,'period_ended':'all','type':'Integrated Filing- Financials','page':1,'size':50}
    r=s.get('https://www.nseindia.com/api/integrated-filing-results',params=p,headers={**UA,'referer':'https://www.nseindia.com/companies-listing/corporate-integrated-filing'},timeout=30);r.raise_for_status();d=r.json();return d.get('data',[])

def fetch_xml(s,url):
    for i in range(5):
        r=s.get(url,headers={**UA,'referer':'https://www.nseindia.com/'},timeout=45)
        if r.status_code==403:
            try:s.get('https://www.nseindia.com/',timeout=15)
            except Exception:pass
            time.sleep(1+i);continue
        r.raise_for_status();return ET.fromstring(r.content)
    raise RuntimeError('xbrl unavailable')

def inspect(s,sym,issuer):
    rows=listing(s,sym,issuer); q=[x for x in rows if str(x.get('qe_Date','')).upper()=='30-JUN-2026']
    cons=[x for x in q if str(x.get('consolidated','')).lower()=='consolidated'];stand=[x for x in q if str(x.get('consolidated','')).lower()=='standalone'];row=(cons or stand)[0]
    root=fetch_xml(s,row['xbrl']);facts=[]
    keys=('profit','loss','equity','capital','facevalue','earning','networth','reserve','share')
    for e in root.iter():
        name=local(e.tag);cr=e.attrib.get('contextRef');txt=(e.text or '').strip()
        if cr and txt and any(k in name.lower() for k in keys):
            try:v=float(txt.replace(',',''))
            except Exception:continue
            facts.append({'name':name,'context':cr,'value':v})
    # dedupe exact triples and keep relevant size manageable
    seen=set();out=[]
    for f in facts:
        k=(f['name'],f['context'],f['value'])
        if k not in seen:seen.add(k);out.append(f)
    return {'basis':row.get('consolidated'),'xbrl':row.get('xbrl'),'facts':out[:250]}

def main():
    s=sess();out={'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'research_only':True,'live_model_changed':False,'cases':{}}
    for sym,issuer in CASES.items():
        try:out['cases'][sym]=inspect(s,sym,issuer)
        except Exception as e:out['cases'][sym]={'error':f'{type(e).__name__}: {e}'}
        time.sleep(.8)
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:('error' if 'error' in v else {'basis':v['basis'],'facts':len(v['facts'])}) for k,v in out['cases'].items()},indent=2))
if __name__=='__main__':main()
