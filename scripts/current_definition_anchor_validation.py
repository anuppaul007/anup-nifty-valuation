#!/usr/bin/env python3
"""All-50 independent current-definition NIFTY 50 anchor validation.

Research only. Reconstructs P/E, P/B and dividend yield for 29-Sep-2023 from
constituent-level official NSE/Nifty data available by that timestamp, then
compares with the published NIFTY 50 ratios. No live model files are changed.

Pre-declared acceptance tolerances (before observing results):
  * P/E relative error <= 1.5%
  * P/B relative error <= 1.5%
  * Dividend-yield absolute error <= 0.05 percentage point
  * 50/50 constituents must pass; otherwise the anchor is incomplete, not pass.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import json, math, re, threading, time, zipfile
import xml.etree.ElementTree as ET

import pandas as pd
import pdfplumber
import requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'current_definition_anchor_validation.json'
SIGNAL=pd.Timestamp('2023-09-29 23:59:59')
TOL={'pe_relative_pct':1.5,'pb_relative_pct':1.5,'dy_absolute_pp':0.05}
UA={'User-Agent':'Mozilla/5.0 (compatible; AnupNiftyValuation/3.6; personal non-commercial research)',
    'Accept':'application/json,text/plain,*/*'}
_TLS=threading.local()


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except Exception:return False


def sess():
    s=getattr(_TLS,'s',None)
    if s is None:
        s=requests.Session();s.headers.update(UA)
        try:s.get('https://www.nseindia.com/',timeout=15)
        except Exception:pass
        _TLS.s=s
    return s


def get_json(url,params=None,tries=3):
    last=None
    for i in range(tries):
        try:
            r=sess().get(url,params=params,headers=UA,timeout=30);r.raise_for_status();return r.json()
        except Exception as e:
            last=e;time.sleep(1.0*(i+1))
    raise last


def parse_dt(x):
    if not x:return None
    return pd.to_datetime(str(x),dayfirst=True,errors='coerce')


def local(tag):return tag.split('}')[-1].split(':')[-1]


def xbrl_root(url):
    r=sess().get(url,headers=UA,timeout=30);r.raise_for_status();return ET.fromstring(r.content)


def contexts(root):
    out={}
    for c in root.iter():
        if local(c.tag)!='context':continue
        cid=c.attrib.get('id'); start=end=instant=None
        for e in c.iter():
            n=local(e.tag)
            if n=='startDate':start=(e.text or '').strip()
            elif n=='endDate':end=(e.text or '').strip()
            elif n=='instant':instant=(e.text or '').strip()
        out[cid]={'start':start,'end':end,'instant':instant}
    return out


def facts(root):
    cs=contexts(root);out=[]
    for e in root.iter():
        cr=e.attrib.get('contextRef'); txt=(e.text or '').strip()
        if not cr or not txt:continue
        try:v=float(txt.replace(',',''))
        except Exception:continue
        out.append({'name':local(e.tag),'value':v,'context':cr,'period':cs.get(cr,{})})
    return out


def match_period(f,from_date,to_date,instant_ok=False):
    p=f['period'];fd=pd.Timestamp(from_date).date().isoformat();td=pd.Timestamp(to_date).date().isoformat()
    if p.get('start')==fd and p.get('end')==td:return True
    if instant_ok and p.get('instant')==td:return True
    return False


def pick_fact(fs,names,from_date,to_date,instant_ok=False):
    norm={n.lower() for n in names}
    cand=[f for f in fs if f['name'].lower() in norm and match_period(f,from_date,to_date,instant_ok)]
    if not cand and instant_ok:
        # some XBRLs put balance-sheet facts in a duration context ending on the annual date
        td=pd.Timestamp(to_date).date().isoformat()
        cand=[f for f in fs if f['name'].lower() in norm and (f['period'].get('end')==td or f['period'].get('instant')==td)]
    return cand[0] if cand else None

PROFIT_NAMES=[
 'ProfitOrLossAttributableToOwnersOfParent',
 'ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates',
 'ProfitLossForThePeriod','ProfitLossForPeriod',
 'ProfitLossFromOrdinaryActivitiesAfterTax',
 'ProfitLossForPeriodFromContinuingAndDiscontinuedOperations',
]
CAP_NAMES=['PaidUpValueOfEquityShareCapital','PaidUpEquityShareCapital']
FACE_NAMES=['FaceValueOfEquityShareCapital','FaceValuePerShare']
EQUITY_DIRECT_NAMES=['EquityAttributableToOwnersOfParent','EquityAttributableToEquityHoldersOfParent','TotalEquityAttributableToOwnersOfParent','NetWorth']
RESERVE_NAMES=['OtherEquity','ReservesAndSurplus','ReserveExcludingRevaluationReserves']


def financial_rows(symbol,period):
    data=get_json('https://www.nseindia.com/api/corporates-financial-results',{'index':'equities','symbol':symbol,'period':period})
    rows=data if isinstance(data,list) else data.get('data',[]) if isinstance(data,dict) else []
    for r in rows:
        r['_filing']=parse_dt(r.get('filingDate') or r.get('broadCastDate'))
        r['_to']=parse_dt(r.get('toDate'));r['_from']=parse_dt(r.get('fromDate'))
    return [r for r in rows if r['_filing'] is not None and r['_filing']<=SIGNAL and isinstance(r.get('xbrl'),str) and r.get('xbrl')]


def choose_basis(rows,to_date=None):
    q=rows
    if to_date is not None:
        td=pd.Timestamp(to_date).date()
        q=[r for r in q if r['_to'] is not None and r['_to'].date()==td]
    if not q:return None
    # revised/latest filing known by signal; consolidated preferred when available for the period
    cons=[r for r in q if str(r.get('consolidated','')).strip().lower()=='consolidated']
    use=cons or [r for r in q if 'non-consolidated' in str(r.get('consolidated','')).lower() or 'standalone' in str(r.get('consolidated','')).lower()] or q
    return sorted(use,key=lambda r:r['_filing'])[-1]


def extract_profit(row):
    root=xbrl_root(row['xbrl']);fs=facts(root)
    f=pick_fact(fs,PROFIT_NAMES,row['_from'],row['_to'])
    if not f:raise ValueError('profit_fact_missing')
    return f['value'],f['name']


def extract_cap_face(row):
    root=xbrl_root(row['xbrl']);fs=facts(root)
    c=pick_fact(fs,CAP_NAMES,row['_from'],row['_to'],True);fv=pick_fact(fs,FACE_NAMES,row['_from'],row['_to'],True)
    if not c or not fv or c['value']<=0 or fv['value']<=0:raise ValueError('capital_or_face_missing')
    return c['value'],fv['value'],c['name'],fv['name']


def extract_networth(row):
    root=xbrl_root(row['xbrl']);fs=facts(root)
    direct=pick_fact(fs,EQUITY_DIRECT_NAMES,row['_from'],row['_to'],True)
    if direct and direct['value']>0:return direct['value'],direct['name'],'direct'
    cap=pick_fact(fs,CAP_NAMES,row['_from'],row['_to'],True)
    reserve=None
    for n in RESERVE_NAMES:
        reserve=pick_fact(fs,[n],row['_from'],row['_to'],True)
        if reserve and reserve['value']>0:break
    if cap and reserve and cap['value']>0:
        return cap['value']+reserve['value'],f"{cap['name']}+{reserve['name']}",'sum'
    raise ValueError('networth_fact_missing')


def parse_dividend(subject,face):
    s=str(subject or '')
    if 'dividend' not in s.lower():return None
    m=re.search(r'(?:Rs\.?|Re\.?|₹)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:per\s*share)?',s,re.I)
    if m:return float(m.group(1))
    m=re.search(r'([0-9]+(?:\.[0-9]+)?)\s*%',s)
    if m and finite(face):return float(m.group(1))*float(face)/100.0
    return None


def dividend_ps(symbol,face):
    start=(SIGNAL.normalize()-pd.DateOffset(years=1)+pd.Timedelta(days=1)).date()
    params={'index':'equities','from_date':start.strftime('%d-%m-%Y'),'to_date':SIGNAL.date().strftime('%d-%m-%Y'),'symbol':symbol}
    data=get_json('https://www.nseindia.com/api/corporates-corporateActions',params)
    rows=data if isinstance(data,list) else data.get('data',[]) if isinstance(data,dict) else []
    vals=[]
    for r in rows:
        ex=parse_dt(r.get('exDate'))
        if ex is None or not(start<=ex.date()<=SIGNAL.date()):continue
        v=parse_dividend(r.get('subject'),r.get('faceVal') or face)
        if v is not None:vals.append({'exDate':str(ex.date()),'subject':r.get('subject'),'amount':v})
    return sum(x['amount'] for x in vals),vals


def weight_rows():
    url='https://www.niftyindices.com/Indices_-_Market_Capitalisation_and_Weightage/indices_dataSep2023.zip'
    r=sess().get(url,timeout=30,headers={**UA,'Referer':'https://www.niftyindices.com/reports/monthly-reports'});r.raise_for_status()
    z=zipfile.ZipFile(BytesIO(r.content));name=next(n for n in z.namelist() if re.search(r'NIFTY_50_Sep2023\.pdf$',n,re.I));pdf=z.read(name)
    rows=[]
    with pdfplumber.open(BytesIO(pdf)) as doc:
        for p in doc.pages:
            tbl=p.extract_table() or []
            for rr in tbl[1:]:
                if not rr or len(rr)<6:continue
                sym=str(rr[0] or '').strip();price=str(rr[3] or '').replace(',','').strip();mcap=str(rr[4] or '').replace(',','').strip();wt=str(rr[5] or '').replace(',','').strip()
                if sym and finite(price) and finite(mcap) and finite(wt):
                    rows.append({'symbol':sym,'name':re.sub(r'\s+',' ',str(rr[1] or '')).strip(),'price':float(price),'index_mcap_cr':float(mcap),'published_weight_pct':float(wt)})
    # unique and exact NIFTY count
    q={r['symbol']:r for r in rows};rows=list(q.values())
    total=sum(r['index_mcap_cr'] for r in rows)
    for r in rows:r['weight']=r['index_mcap_cr']/total
    return rows,{'url':url,'pdf':name,'count':len(rows),'index_mcap_cr_sum':total,'published_weight_sum':sum(r['published_weight_pct'] for r in rows)}


def reconstruct_symbol(r):
    sym=r['symbol'];qrows=financial_rows(sym,'Quarterly');arows=financial_rows(sym,'Annual')
    q_by_to={}
    for row in qrows:
        if row['_to'] is not None:q_by_to.setdefault(row['_to'].date(),[]).append(row)
    eligible_dates=sorted([d for d in q_by_to if d<=SIGNAL.date()],reverse=True)
    picked=[]
    for d in eligible_dates:
        row=choose_basis(q_by_to[d])
        if not row:continue
        # keep true ~quarter durations; API can contain duplicates/odd periods
        if row['_from'] is None or row['_to'] is None:continue
        days=(row['_to']-row['_from']).days+1
        if 70<=days<=110:picked.append(row)
        if len(picked)==4:break
    if len(picked)!=4:raise ValueError(f'quarter_count={len(picked)}')
    profits=[];profit_tags=[]
    for row in picked:
        v,n=extract_profit(row);profits.append(v);profit_tags.append({'toDate':str(row['_to'].date()),'filingDate':str(row['_filing']),'basis':row.get('consolidated'),'tag':n,'xbrl':row['xbrl']})
    # latest point-in-time share capital source
    latest=max(picked,key=lambda x:x['_filing']);cap,face,ct,ft=extract_cap_face(latest);shares=cap/face
    # latest annual report filed by signal, same consolidated preference rule
    annual=choose_basis(arows)
    if not annual:raise ValueError('annual_missing')
    networth,nw_tag,nw_mode=extract_networth(annual)
    divps,divs=dividend_ps(sym,face)
    full_mcap=float(r['price'])*shares
    ttm=sum(profits)
    if min(full_mcap,shares,networth)<=0:raise ValueError('nonpositive_denominator')
    return {**r,'status':'ok','ttm_profit':ttm,'share_count':shares,'paid_up_capital':cap,'face_value':face,'full_mcap':full_mcap,
            'earnings_yield':ttm/full_mcap,'book_yield':networth/full_mcap,'dividend_ps_12m':divps,'dividend_yield_pct':100*divps/float(r['price']),
            'profit_quarters':profit_tags,'annual':{'toDate':str(annual['_to'].date()) if annual['_to'] is not None else None,'filingDate':str(annual['_filing']),'basis':annual.get('consolidated'),'networth_tag':nw_tag,'networth_mode':nw_mode,'xbrl':annual['xbrl']},'dividends':divs}


def published_ratios():
    from jugaad_data.nse import index_pe_raw
    rows=index_pe_raw('NIFTY 50',date(2023,9,29),date(2023,9,29)) or []
    if not rows:raise RuntimeError('published ratio unavailable')
    x=rows[0]
    def num(keys):
        for k in keys:
            if k in x and x[k] not in (None,'','-'):
                try:return float(str(x[k]).replace(',','').replace('%',''))
                except Exception:pass
        return None
    return {'raw':x,'pe':num(['P/E','PE','pe']),'pb':num(['P/B','PB','pb']),'dy':num(['Div Yield %','Div Yield','Dividend Yield','DY','divYield'])}


def main():
    rows,weight_meta=weight_rows();errors=[];done=[]
    with ThreadPoolExecutor(max_workers=5) as ex:
        fut={ex.submit(reconstruct_symbol,r):r['symbol'] for r in rows}
        for f in as_completed(fut):
            try:done.append(f.result())
            except Exception as e:errors.append({'symbol':fut[f],'error':f'{type(e).__name__}: {e}'})
    done=sorted(done,key=lambda r:r['symbol']);errors=sorted(errors,key=lambda r:r['symbol'])
    pub=published_ratios();result=None
    if len(done)==50 and not errors:
        pe=1.0/sum(r['weight']*r['earnings_yield'] for r in done)
        pb=1.0/sum(r['weight']*r['book_yield'] for r in done)
        dy=sum(r['weight']*r['dividend_yield_pct'] for r in done)
        pe_err=100*(pe/pub['pe']-1);pb_err=100*(pb/pub['pb']-1);dy_err=dy-pub['dy']
        result={'reconstructed':{'pe':pe,'pb':pb,'dy':dy},'published':{k:pub[k] for k in ('pe','pb','dy')},
                'errors':{'pe_relative_pct':pe_err,'pb_relative_pct':pb_err,'dy_absolute_pp':dy_err},
                'pass':abs(pe_err)<=TOL['pe_relative_pct'] and abs(pb_err)<=TOL['pb_relative_pct'] and abs(dy_err)<=TOL['dy_absolute_pp']}
    out={'schema_version':1,'generated_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'research_only':True,
         'signal_date':'2023-09-29','predeclared_tolerances':TOL,'weight_source':weight_meta,'coverage':{'ok':len(done),'required':50,'failed':len(errors)},
         'result':result,'failed_constituents':errors,'constituents':done,'published_raw':pub['raw'],'live_model_changed':False,'live_allocation_changed':False}
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps({'coverage':out['coverage'],'result':result,'live_model_changed':False},default=str))
    # Network/accounting coverage gaps are evidence, not CI failure. Structural source errors are caught by tests.

if __name__=='__main__':main()
