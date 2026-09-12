"""India domestic macro block for Anup Nifty Valuation V3.6.

Current CPI and IIP are sourced from official Government of India PIB releases
issued by MoSPI/NSO. The adapter discovers newer releases from PIB's current-
month All Releases page, while retaining the last verified release URL from the
previous successful model run. This avoids hard-coding the data values and also
avoids depending on the currently unstable authenticated eSankhyiki API.

Scores use explicit economic anchors:
- CPI vs RBI's 4% inflation target
- IIP growth vs a 5% medium-growth anchor
- real policy repo rate vs a 1% reference
"""
from __future__ import annotations
from datetime import date
from urllib.parse import urljoin
import math,re
import numpy as np
import pandas as pd
from lxml import html
import http_client as requests

UA={'User-Agent':'Mozilla/5.0 (compatible; AnupNiftyValuation/3.6; personal research)'}
RBI='https://www.rbi.org.in/'
PIB_ALL='https://www.pib.gov.in/AllRelease.aspx?MenuId=22&PMO=1&lang=1&reg=1'
PIB_BASE='https://www.pib.gov.in/'
# Bootstrap URLs are official release pages, not hard-coded economic values.
# Thereafter the prior successful source URL is carried forward automatically
# until PIB publishes a newer matching release in the current month.
PIB_SEED={
    'cpi':'https://www.pib.gov.in/PressReleasePage.aspx?PRID=2298247',
    'iip':'https://www.pib.gov.in/PressReleasePage.aspx?PRID=2304222',
}


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (TypeError,ValueError):return False

def fresh(asof,max_age):
    try:
        age=(date.today()-date.fromisoformat(str(asof)[:10])).days
        return 0<=age<=max_age
    except (TypeError,ValueError):return False

def period_end(month,year):
    if isinstance(month,(int,float,np.integer,np.floating)) or str(month).strip().isdigit():mm=int(float(month))
    else:mm=pd.to_datetime(str(month).strip(),format='%B').month
    return pd.Period(f'{int(year):04d}-{mm:02d}',freq='M').end_time.date().isoformat()
def clean_text(text):
    try:return ' '.join(html.fromstring(str(text)).text_content().split())
    except Exception:return ' '.join(str(text).split())
def _dedupe(xs):
    seen=set();out=[]
    for x in xs:
        if x and x not in seen:seen.add(x);out.append(x)
    return out

def parse_cpi(text,source_url=None):
    page=clean_text(text)
    pats=[
      r'Retail inflation based on Consumer Price Index in\s+([A-Za-z]+),?\s+(\d{4})\s+is\s+(-?\d+(?:\.\d+)?)\s*%',
      r'Year[- ]on[- ]year inflation rate based on All India Consumer Price Index.*?(?:month of|for)\s+([A-Za-z]+),?\s+(\d{4}).{0,320}?(?:is|stood at|estimated at)\s+(-?\d+(?:\.\d+)?)\s*%',
      r'CONSUMER PRICE INDEX.*?FOR\s+([A-Za-z]+),?\s+(\d{4}).{0,500}?inflation.{0,120}?(-?\d+(?:\.\d+)?)\s*%',
    ]
    match=None
    for p in pats:
        match=re.search(p,page,re.I)
        if match:break
    if not match:raise RuntimeError('All-India CPI inflation not parsed from official PIB release')
    month,year,value=match.groups();value=float(value)
    if not -5<value<30:raise RuntimeError('CPI inflation outside validation range')
    asof=period_end(month,year)
    return {'value':value,'asof':asof,'source_url':source_url,'status':'live' if fresh(asof,75) else 'stale','label':'All-India CPI inflation, YoY','source':'MoSPI/NSO via PIB'}

def parse_iip(text,source_url=None):
    page=clean_text(text)
    pats=[
      r'IIP growth rate for the month of\s+([A-Za-z]+)\s+(\d{4})\s+is\s+(-?\d+(?:\.\d+)?)\s*(?:percent|%)',
      r'Index of Industrial Production.*?(?:recorded|records|growth of|grew by).{0,80}?(-?\d+(?:\.\d+)?)\s*%.*?(?:in|during)\s+([A-Za-z]+)\s+(\d{4})',
    ]
    m=re.search(pats[0],page,re.I)
    if m:month,year,value=m.groups()
    else:
        m=re.search(pats[1],page,re.I)
        if not m:raise RuntimeError('India IIP growth not parsed from official PIB release')
        value,month,year=m.groups()
    value=float(value)
    if not -30<value<40:raise RuntimeError('IIP growth outside validation range')
    asof=period_end(month,year)
    return {'value':value,'asof':asof,'source_url':source_url,'status':'live' if fresh(asof,90) else 'stale','label':'India IIP growth, YoY','source':'MoSPI/NSO via PIB'}

def parse_repo(text,source_url=RBI):
    page=clean_text(text)
    section=re.search(r'Policy\s+Rates(.*?)(?:Reserve\s+Ratios|Exchange\s+Rates)',page,re.I);target=section.group(1) if section else page
    m=re.search(r'Policy\s+Repo\s+Rate\s*:?\s*(\d+(?:\.\d+)?)\s*%',target,re.I)
    if not m:raise RuntimeError('RBI policy repo rate not parsed')
    value=float(m.group(1))
    if not 1<value<15:raise RuntimeError('Repo rate outside validation range')
    return {'value':value,'asof':date.today().isoformat(),'source_url':source_url,'status':'live','label':'RBI policy repo rate','date_basis':'retrieval date; current policy rate remains effective until changed'}

def _link_matches(kind,text):
    s=' '.join(str(text).lower().split())
    if kind=='cpi':
        return ('consumer price index' in s or re.search(r'\bcpi\b',s)) and any(k in s for k in ('press release','inflation','consumer price index'))
    return ('industrial production' in s or re.search(r'\biip\b',s)) and any(k in s for k in ('quick estimate','growth','industrial production','iip'))

def pib_links_from_html(kind,text):
    """Extract candidate official release links from PIB's current-month page."""
    tree=html.fromstring(text);out=[]
    for a in tree.xpath('//a[@href]'):
        href=urljoin(PIB_BASE,a.get('href') or '')
        own=' '.join(a.text_content().split())
        parent=' '.join(a.getparent().text_content().split()) if a.getparent() is not None else ''
        context=f'{own} {parent}'
        if _link_matches(kind,context) and any(k.lower() in href.lower() for k in ('pressrelease','pressrelese','erelcontent')):
            out.append(href)
    return _dedupe(out)

def discover_pib_links(kind):
    try:
        r=requests.get(PIB_ALL,headers=UA,timeout=25);r.raise_for_status();return pib_links_from_html(kind,r.text)
    except Exception:return []

def _prior_source(prior,kind):
    try:
        key='india_cpi_yoy' if kind=='cpi' else 'india_iip_yoy'
        return (((prior or {}).get('factors') or {}).get(key) or {}).get('source_url')
    except Exception:return None

def fetch_release(kind,parser,prior=None):
    """Fetch newest parseable official release without inventing missing data."""
    candidates=_dedupe(discover_pib_links(kind)+[_prior_source(prior,kind),PIB_SEED[kind]])
    parsed=[];errors=[]
    for url in candidates:
        try:
            r=requests.get(url,headers=UA,timeout=25);r.raise_for_status();x=parser(r.text,url)
            parsed.append(x)
        except Exception as e:errors.append(f'{url}: {type(e).__name__}: {e}')
    if not parsed:raise RuntimeError(f'No parseable official PIB {kind.upper()} release; ' + ' | '.join(errors[-3:]))
    return max(parsed,key=lambda x:x['asof'])

def fetch_repo():
    r=requests.get(RBI,headers=UA,timeout=25);r.raise_for_status();return parse_repo(r.text,RBI)

def build(prior=None):
    cpi=fetch_release('cpi',parse_cpi,prior);iip=fetch_release('iip',parse_iip,prior);repo=fetch_repo()
    if any(x.get('status')!='live' or not finite(x.get('value')) for x in (cpi,iip,repo)):
        raise RuntimeError('India domestic macro source is stale or unavailable')
    inflation_gap=float(cpi['value'])-4.0;real_repo=float(repo['value'])-float(cpi['value'])
    inflation_score=float(np.tanh(-inflation_gap/1.5))
    activity_score=float(np.tanh((float(iip['value'])-5.0)/4.0))
    policy_score=float(np.tanh(-(real_repo-1.0)/1.5))
    score=.40*inflation_score+.35*activity_score+.25*policy_score
    factors={
      'india_cpi_yoy':dict(cpi,score=inflation_score,reference=4.0,reference_label='RBI inflation target'),
      'india_iip_yoy':dict(iip,score=activity_score,reference=5.0,reference_label='medium-growth anchor'),
      'india_repo_rate':dict(repo,score=policy_score,real_repo=real_repo,reference_real_rate=1.0,reference_label='real policy-rate anchor')
    }
    return {'score':float(score),'coverage':1.0,'status':'live','factors':factors,'inflation_gap_pp':inflation_gap,'real_repo_rate':real_repo,'method':'economic-anchor-v1','source_policy':'official-PIB-discovery-with-prior-release-carry-forward'}
