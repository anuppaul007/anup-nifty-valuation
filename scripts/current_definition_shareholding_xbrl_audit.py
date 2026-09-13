#!/usr/bin/env python3
"""Compare financial-result share counts with official Jun-2026 shareholding XBRL.

Research only. The prior IWF upper-bound audit proved that eight constituents
produce an inferred index IWF above official public shareholding when statutory
shares are derived from financial-result paid-up capital / face value. This
script inspects the official NSE Shareholding Pattern XBRL for those same names
and extracts share/capital-like numeric facts. It does not choose a replacement
share count by closeness to NIFTY ratios.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import json,re,time,xml.etree.ElementTree as ET
import pandas as pd
import current_definition_integrated_anchor_v5 as v5
import current_definition_iwf_upper_bound_audit as iwf

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_shareholding_xbrl_audit.json'
a=v5.a
SYMBOLS=['BEL','HINDALCO','INFY','M&M','MARUTI','RELIANCE','SBIN','TECHM']


def local(tag):return tag.split('}')[-1].split(':')[-1]


def fetch_xml(s,url):
    last=None
    for attempt in range(6):
        try:
            r=s.get(url,headers={**a.UA,'referer':'https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern','accept':'application/xml,text/xml,*/*'},timeout=40)
            if r.status_code in (401,403,500):
                try:s.get('https://www.nseindia.com/',timeout=15)
                except Exception:pass
                time.sleep(1+attempt*.6);continue
            r.raise_for_status();return ET.fromstring(r.content)
        except Exception as e:last=e;time.sleep(.7+attempt*.6)
    raise last or RuntimeError('shareholding_xbrl_unavailable')


def context_map(root):
    out={}
    for c in root.iter():
        if local(c.tag)!='context':continue
        cid=str(c.attrib.get('id') or '');instant=start=end=None;dims=[]
        for e in c.iter():
            n=local(e.tag)
            if n=='instant':instant=(e.text or '').strip()
            elif n=='startDate':start=(e.text or '').strip()
            elif n=='endDate':end=(e.text or '').strip()
            elif n in ('explicitMember','typedMember'):dims.append({'dimension':e.attrib.get('dimension'),'value':(e.text or '').strip()})
        out[cid]={'instant':instant,'start':start,'end':end,'dimensions':dims}
    return out


def share_like(name):
    n=name.lower()
    positive=('share','capital','paidup','paid_up','equity')
    negative=('percentage','percent','voting','encumbered','pledged','convertible','warrant','esop','shareholder')
    return any(k in n for k in positive) and not any(k in n for k in negative)


def numeric_facts(root):
    ctx=context_map(root);out=[]
    for e in root.iter():
        cr=e.attrib.get('contextRef');txt=(e.text or '').strip();name=local(e.tag)
        if not cr or not txt or not share_like(name):continue
        try:v=float(txt.replace(',',''))
        except Exception:continue
        out.append({'name':name,'context':str(cr),'value':v,'unitRef':e.attrib.get('unitRef'),'decimals':e.attrib.get('decimals'),'period':ctx.get(str(cr))})
    return sorted(out,key=lambda x:(x['name'],x['context'],x['value']))


def june_row(rows):
    for r in rows:
        d=iwf.parse_dt(r.get('date') or r.get('asOnDate') or r.get('as_on_date'))
        if d is not None and d.date()==pd.Timestamp('2026-06-30').date():return r
    return None


def financial_structure(s,row):
    listings,issuer=a.listings_for(s,row);parsed={}
    for q in ('31-MAR-2026','30-JUN-2026'):
        sel,basis=a.choose_quarter(listings,q)
        if not sel:raise ValueError('missing_'+q)
        parsed[q]=a.numeric_facts(a.fetch_xml(s,sel['xbrl']));time.sleep(.15)
    actions=a.corporate_actions(s,row['symbol'])
    c,fv,src,structure,attempts=v5.choose_structure(row,parsed,actions)
    return {'financial_share_count':structure['shares'],'financial_paid_up_capital':c['value'],'financial_face_value':fv['value'],'financial_capital_tag':c['name'],'financial_share_source':src,'financial_attempts':attempts}


def candidate_summary(facts,financial_shares):
    # Surface only positive share-like counts in a broad but reproducible range;
    # do not pick the candidate closest to any index target.
    vals=[]
    for f in facts:
        v=float(f['value'])
        if v<=0:continue
        # Shares may be reported in absolute units while rupee capital can also
        # appear; retain both but flag ratios to the independent financial count.
        vals.append({**f,'ratio_to_financial_share_count':v/financial_shares if financial_shares else None})
    return vals


def main():
    s=a.cov.session();weights,wmeta=a.cov.weight_rows(s);by={r['symbol']:r for r in weights};done={};errors=[]
    for sym in SYMBOLS:
        try:
            row=by[sym];fin=financial_structure(s,row);shr_rows=iwf.shareholding_rows(s,sym);jr=june_row(shr_rows)
            if not jr:raise ValueError('june_shareholding_row_missing')
            url=jr.get('xbrl')
            if not url:raise ValueError('shareholding_xbrl_url_missing')
            root=fetch_xml(s,url);facts=numeric_facts(root)
            done[sym]={**row,**fin,'shareholding_xbrl':url,'shareholding_submission':jr.get('submissionDate'),'public_pct':iwf.fnum(jr.get('public_val')),'promoter_pct':iwf.fnum(jr.get('pr_and_prgrp')),'employee_trust_pct':iwf.fnum(jr.get('employeeTrusts')),'share_like_facts':candidate_summary(facts,fin['financial_share_count'])}
        except Exception as e:errors.append({'symbol':sym,'error':f'{type(e).__name__}: {e}'})
        time.sleep(.35)
    out={'schema_version':1,'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'research_only':True,'anchor_date':'2026-08-31','shareholding_quarter':'2026-06-30','symbols':SYMBOLS,'coverage':{'ok':len(done),'required':len(SYMBOLS),'failed':len(errors)},'failed':errors,'cases':done,'interpretation_guardrail':'Shareholding XBRL is an independent statutory source. Candidate facts are surfaced by semantic tag filtering only; no candidate is selected by closeness to NIFTY P/E/P/B/IWF.','live_model_changed':False,'live_allocation_changed':False,'tolerances_changed':False}
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    headline={}
    for sym,v in done.items():
        headline[sym]={'financial_shares':v['financial_share_count'],'facts':[{'name':f['name'],'context':f['context'],'value':f['value'],'unitRef':f['unitRef'],'ratio':f['ratio_to_financial_share_count']} for f in v['share_like_facts'][:25]]}
    print(json.dumps({'coverage':out['coverage'],'headline':headline,'failed':errors},indent=2))

if __name__=='__main__':main()
