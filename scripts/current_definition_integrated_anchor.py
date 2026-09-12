#!/usr/bin/env python3
"""Strict 50/50 current-definition NIFTY 50 anchor at 31-Aug-2026.

Research-only independent reconstruction using:
- official Aug-2026 NIFTY 50 constituent weights / close prices;
- four NSE Integrated Filing quarters (Sep-2025 through Jun-2026), with
  consolidated results preferred and standalone used only when consolidated is
  unavailable for that issuer/quarter;
- latest annual (Mar-2026) equity/net worth from the same filing set;
- rolling 12-month dividends from official NSE corporate actions;
- only filings created/broadcast no later than the anchor timestamp.

Pre-declared acceptance tolerances remain identical to the Sep-2023 pilot:
P/E and P/B <= 1.5% relative error; dividend yield <= 0.05 percentage point.
No live model/allocation files are modified.
"""
from __future__ import annotations
from datetime import date,datetime,timezone
from pathlib import Path
import json,math,re,time,xml.etree.ElementTree as ET
import pandas as pd
import requests
import current_definition_integrated_coverage as cov

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_integrated_anchor.json'
ANCHOR=pd.Timestamp('2026-08-31 23:59:59')
TARGET=['30-SEP-2025','31-DEC-2025','31-MAR-2026','30-JUN-2026']
TOL={'pe_relative_pct':1.5,'pb_relative_pct':1.5,'dy_absolute_pp':0.05}
UA=cov.UA

PROFIT_NAMES=[
 'ProfitOrLossAttributableToOwnersOfParent','ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates',
 'ProfitLossForThePeriod','ProfitLossForPeriod','ProfitLossFromOrdinaryActivitiesAfterTax',
 'ProfitLossForPeriodFromContinuingAndDiscontinuedOperations','ProfitAfterTax'
]
CAP_NAMES=['PaidUpValueOfEquityShareCapital','PaidUpEquityShareCapital','EquityShareCapital']
FACE_NAMES=['FaceValueOfEquityShareCapital','FaceValuePerShare']
EQUITY_NAMES=['EquityAttributableToOwnersOfParent','TotalEquityAttributableToOwnersOfParent','Equity','NetWorth','TotalEquity']
OTHER_EQUITY_NAMES=['OtherEquity','ReservesAndSurplus','ReserveExcludingRevaluationReserves']


def local(tag):return tag.split('}')[-1].split(':')[-1]
def parse_dt(x):
    if not x:return None
    d=pd.to_datetime(str(x),dayfirst=True,errors='coerce')
    return None if pd.isna(d) else d

def filing_time(row):
    for k in ('revised_Date','creation_Date','broadcast_Date'):
        d=parse_dt(row.get(k))
        if d is not None:return d
    return None

def eligible_rows(rows):
    out=[]
    for r in rows:
        t=filing_time(r)
        if t is not None and t<=ANCHOR:out.append(r)
    return out

def choose_quarter(rows,q):
    qr=[x for x in eligible_rows(rows) if str(x.get('qe_Date') or '').upper().strip()==q]
    cons=[x for x in qr if str(x.get('consolidated') or '').strip().lower()=='consolidated']
    stand=[x for x in qr if str(x.get('consolidated') or '').strip().lower()=='standalone']
    pool=cons or stand
    if not pool:return None,None
    pool=sorted(pool,key=lambda x:filing_time(x) or pd.Timestamp.min)
    return pool[-1],('consolidated' if cons else 'standalone_fallback')

def fetch_xml(s,url):
    last=None
    for attempt in range(7):
        try:
            r=s.get(url,headers={**UA,'referer':'https://www.nseindia.com/companies-listing/corporate-integrated-filing','accept':'application/xml,text/xml,*/*'},timeout=45)
            if r.status_code in (401,403,500):
                try:s.get('https://www.nseindia.com/',timeout=15)
                except Exception:pass
                time.sleep(1.0+attempt*.7);continue
            r.raise_for_status();return ET.fromstring(r.content)
        except Exception as e:
            last=e;time.sleep(.7+attempt*.5)
    raise last or RuntimeError('xbrl_unavailable')

def numeric_facts(root):
    out=[]
    for e in root.iter():
        cr=e.attrib.get('contextRef');txt=(e.text or '').strip()
        if not cr or not txt:continue
        try:v=float(txt.replace(',',''))
        except Exception:continue
        out.append({'name':local(e.tag),'context':str(cr),'value':v})
    return out

def pick(fs,names,contexts):
    for name in names:
        q=[f for f in fs if f['name'].lower()==name.lower() and f['context'].lower() in {x.lower() for x in contexts}]
        if not q:continue
        vals={round(float(x['value']),6) for x in q}
        if len(vals)==1:return q[0]
        # prefer the canonical context order supplied by caller
        for c in contexts:
            qc=[x for x in q if x['context'].lower()==c.lower()]
            if qc:
                vals2={round(float(x['value']),6) for x in qc}
                if len(vals2)==1:return qc[0]
    return None

def profit_from(fs):
    f=pick(fs,PROFIT_NAMES,['OneD'])
    if not f:raise ValueError('profit_fact_missing')
    return f

def cap_face_from(fs):
    c=pick(fs,CAP_NAMES,['OneD','FourD','OneI']);fv=pick(fs,FACE_NAMES,['OneD','FourD','OneI'])
    if not c or not fv or c['value']<=0 or fv['value']<=0:raise ValueError('capital_or_face_missing')
    return c,fv

def networth_from(fs):
    f=pick(fs,EQUITY_NAMES,['OneI'])
    if f and f['value']>0:return f,'direct'
    cap=pick(fs,CAP_NAMES,['OneI']);other=pick(fs,OTHER_EQUITY_NAMES,['OneI'])
    if cap and other and cap['value']>0 and other['value']>=0:
        return {'name':cap['name']+'+'+other['name'],'context':'OneI','value':cap['value']+other['value']},'sum'
    raise ValueError('networth_fact_missing')

def parse_dividend(subject,face):
    s=str(subject or '')
    if 'dividend' not in s.lower():return None
    m=re.search(r'(?:Rs\.?|Re\.?|₹)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:per\s*share)?',s,re.I)
    if m:return float(m.group(1))
    m=re.search(r'([0-9]+(?:\.[0-9]+)?)\s*%',s)
    if m and face>0:return float(m.group(1))*face/100.0
    return None

def dividends(s,symbol,face):
    start=date(2025,9,1);end=date(2026,8,31)
    p={'index':'equities','from_date':start.strftime('%d-%m-%Y'),'to_date':end.strftime('%d-%m-%Y'),'symbol':symbol}
    rows=[]
    for attempt in range(4):
        try:
            r=s.get('https://www.nseindia.com/api/corporates-corporateActions',params=p,headers={**UA,'referer':'https://www.nseindia.com/companies-listing/corporate-filings-actions'},timeout=30)
            if r.status_code in (401,403,500):
                try:s.get('https://www.nseindia.com/',timeout=15)
                except Exception:pass
                time.sleep(1+attempt);continue
            r.raise_for_status();d=r.json();rows=d if isinstance(d,list) else d.get('data',[]) if isinstance(d,dict) else [];break
        except Exception:
            time.sleep(1+attempt)
    vals=[]
    for r in rows:
        ex=parse_dt(r.get('exDate'))
        if ex is None or not(start<=ex.date()<=end):continue
        v=parse_dividend(r.get('subject'),float(r.get('faceVal') or face))
        if v is not None:vals.append({'exDate':str(ex.date()),'subject':r.get('subject'),'amount':v})
    return sum(x['amount'] for x in vals),vals

def listings_for(s,row):
    best=[];issuer=None
    for name in cov.issuer_variants(row['security_name'])+['']:
        q=cov.listing(s,row['symbol'],name)
        if len(q)>len(best):best=q;issuer=name
        if q:break
    return best,issuer

def reconstruct_one(s,row):
    listings,issuer=listings_for(s,row);selected={};basis={}
    for q in TARGET:
        r,b=choose_quarter(listings,q)
        if not r:raise ValueError('missing_integrated_quarter_'+q)
        selected[q]=r;basis[q]=b
    parsed={}
    for q in TARGET:
        root=fetch_xml(s,selected[q]['xbrl']);parsed[q]=numeric_facts(root);time.sleep(.22)
    profits=[];profit_meta=[]
    for q in TARGET:
        f=profit_from(parsed[q]);profits.append(f['value']);profit_meta.append({'quarter':q,'basis':basis[q],'tag':f['name'],'context':f['context'],'filing_time':str(filing_time(selected[q])),'xbrl':selected[q]['xbrl']})
    c,fv=cap_face_from(parsed['30-JUN-2026']);shares=c['value']/fv['value']
    nw,nwmode=networth_from(parsed['31-MAR-2026'])
    if shares<=0 or nw['value']<=0:raise ValueError('nonpositive_structure')
    full_mcap=row['price']*shares;ttm=sum(profits)
    if full_mcap<=0 or ttm<=0:raise ValueError('nonpositive_earnings_or_mcap')
    dps,divs=dividends(s,row['symbol'],fv['value'])
    return {**row,'status':'ok','issuer_used':issuer,'basis_by_quarter':basis,'ttm_profit':ttm,'share_count':shares,'paid_up_capital':c['value'],'face_value':fv['value'],'capital_tag':c['name'],'face_tag':fv['name'],'full_mcap':full_mcap,'earnings_yield':ttm/full_mcap,'networth':nw['value'],'networth_tag':nw['name'],'networth_mode':nwmode,'book_yield':nw['value']/full_mcap,'dividend_ps_12m':dps,'dividend_yield_pct':100*dps/row['price'],'profit_quarters':profit_meta,'dividends':divs}

def published_ratios():
    from jugaad_data.nse import index_pe_raw
    rows=index_pe_raw('NIFTY 50',date(2026,8,31),date(2026,8,31)) or []
    if not rows:raise RuntimeError('published_ratio_unavailable')
    x=rows[0]
    def num(keys):
        for k in keys:
            if k in x and x[k] not in (None,'','-'):
                try:return float(str(x[k]).replace(',','').replace('%',''))
                except Exception:pass
        return None
    return {'raw':x,'pe':num(['P/E','PE','pe']),'pb':num(['P/B','PB','pb']),'dy':num(['Div Yield %','Div Yield','Dividend Yield','DY','divYield'])}

def main():
    s=cov.session();rows,weight_meta=cov.weight_rows(s);done=[];errors=[]
    for i,row in enumerate(rows):
        try:done.append(reconstruct_one(s,row))
        except Exception as e:errors.append({'symbol':row['symbol'],'error':f'{type(e).__name__}: {e}'})
        time.sleep(.28)
    done=sorted(done,key=lambda x:x['symbol']);errors=sorted(errors,key=lambda x:x['symbol']);pub=published_ratios();result=None
    if len(done)==50 and not errors:
        total=sum(x['index_mcap_cr'] for x in done)
        for x in done:x['weight']=x['index_mcap_cr']/total
        pe=1/sum(x['weight']*x['earnings_yield'] for x in done)
        pb=1/sum(x['weight']*x['book_yield'] for x in done)
        dy=sum(x['weight']*x['dividend_yield_pct'] for x in done)
        err={'pe_relative_pct':100*abs(pe-pub['pe'])/pub['pe'] if pub['pe'] else None,'pb_relative_pct':100*abs(pb-pub['pb'])/pub['pb'] if pub['pb'] else None,'dy_absolute_pp':abs(dy-pub['dy']) if pub['dy'] is not None else None}
        passed=all([err['pe_relative_pct'] is not None and err['pe_relative_pct']<=TOL['pe_relative_pct'],err['pb_relative_pct'] is not None and err['pb_relative_pct']<=TOL['pb_relative_pct'],err['dy_absolute_pp'] is not None and err['dy_absolute_pp']<=TOL['dy_absolute_pp']])
        result={'reconstructed':{'pe':pe,'pb':pb,'dy':dy},'published':{'pe':pub['pe'],'pb':pub['pb'],'dy':pub['dy']},'errors':err,'passed':passed}
    out={'schema_version':1,'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'research_only':True,'anchor_date':'2026-08-31','predeclared_tolerances':TOL,'basis_rule':'consolidated when available; standalone only when consolidated unavailable','weight_source':weight_meta,'coverage':{'ok':len(done),'required':50,'failed':len(errors)},'result':result,'failed_constituents':errors,'constituents':done,'published_raw':pub['raw'],'live_model_changed':False,'live_allocation_changed':False}
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps({'coverage':out['coverage'],'result':result,'failures':errors[:15]},indent=2))

if __name__=='__main__':main()
