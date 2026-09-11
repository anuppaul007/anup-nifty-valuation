"""India domestic macro block for Anup Nifty Valuation V3.6.

Uses current official Indian sources only:
- MoSPI/PIB Consumer Price Index release
- MoSPI/PIB Index of Industrial Production release
- RBI current policy repo rate

Scores are anchored to economic reference points rather than short histories:
4% CPI target, 5% IIP growth and a 1% real policy-rate reference. This avoids
calling a short post-rebase history a statistically calibrated z-score.
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
PIB_LIST='https://www.pib.gov.in/newsite/pmreleases.aspx?lang=2&mincode=55&reg=48'
RBI='https://www.rbi.org.in/'


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (TypeError,ValueError):return False

def fresh(asof,max_age):
    try:
        age=(date.today()-date.fromisoformat(str(asof)[:10])).days
        return 0<=age<=max_age
    except (TypeError,ValueError):return False

def period_end(month,year):
    return pd.Period(f'{int(year):04d}-{pd.to_datetime(month,format="%B").month:02d}',freq='M').end_time.date().isoformat()

def clean_text(text):return ' '.join(html.fromstring(text).text_content().split())

def discover_release(kind):
    r=requests.get(PIB_LIST,headers=UA,timeout=25);r.raise_for_status();tree=html.fromstring(r.text)
    found=[]
    for a in tree.xpath('//a[@href]'):
        title=' '.join(a.text_content().split());low=title.lower();href=a.get('href') or ''
        if kind=='cpi':ok='consumer price index' in low and ('release' in low or 'cpi' in low)
        else:ok='industrial production' in low and ('index' in low or 'iip' in low)
        if ok and href:found.append((title,urljoin(PIB_LIST,href)))
    if not found:raise RuntimeError(f'PIB {kind.upper()} release link not found')
    return found[0]

def parse_cpi(text,source_url=None):
    page=clean_text(text)
    pats=[
      r'Retail inflation based on Consumer Price Index in\s+([A-Za-z]+),?\s+(\d{4})\s+is\s+(-?\d+(?:\.\d+)?)\s*%',
      r'Year-on-year inflation rate based on All India Consumer Price Index.*?month of\s+([A-Za-z]+),?\s+(\d{4}).{0,180}?is\s+(-?\d+(?:\.\d+)?)\s*%'
    ]
    match=None
    for p in pats:
        match=re.search(p,page,re.I)
        if match:break
    if not match:raise RuntimeError('All-India CPI inflation not parsed')
    month,year,value=match.groups();value=float(value)
    if not -5<value<30:raise RuntimeError('CPI inflation outside validation range')
    asof=period_end(month,year)
    return {'value':value,'asof':asof,'source_url':source_url,'status':'live' if fresh(asof,75) else 'stale','label':'All-India CPI inflation, YoY'}

def parse_iip(text,source_url=None):
    page=clean_text(text)
    p1=r'IIP growth rate for the month of\s+([A-Za-z]+)\s+(\d{4})\s+is\s+(-?\d+(?:\.\d+)?)\s*(?:percent|%)'
    p2=r'Index of industrial production records growth of\s+(-?\d+(?:\.\d+)?)\s*%\s+in\s+([A-Za-z]+)\s+(\d{4})'
    m=re.search(p1,page,re.I)
    if m:month,year,value=m.groups()
    else:
        m=re.search(p2,page,re.I)
        if not m:raise RuntimeError('India IIP growth not parsed')
        value,month,year=m.groups()
    value=float(value)
    if not -30<value<40:raise RuntimeError('IIP growth outside validation range')
    asof=period_end(month,year)
    return {'value':value,'asof':asof,'source_url':source_url,'status':'live' if fresh(asof,90) else 'stale','label':'India IIP growth, YoY'}

def parse_repo(text,source_url=RBI):
    page=clean_text(text)
    section=re.search(r'Policy\s+Rates(.*?)(?:Reserve\s+Ratios|Exchange\s+Rates)',page,re.I)
    target=section.group(1) if section else page
    m=re.search(r'Policy\s+Repo\s+Rate\s*:?\s*(\d+(?:\.\d+)?)\s*%',target,re.I)
    if not m:raise RuntimeError('RBI policy repo rate not parsed')
    value=float(m.group(1))
    if not 1<value<15:raise RuntimeError('Repo rate outside validation range')
    return {'value':value,'asof':date.today().isoformat(),'source_url':source_url,'status':'live','label':'RBI policy repo rate','date_basis':'retrieval date; current policy rate remains effective until changed'}

def fetch_release(kind,parser):
    _,url=discover_release(kind);r=requests.get(url,headers=UA,timeout=25);r.raise_for_status();return parser(r.text,url)

def fetch_repo():
    r=requests.get(RBI,headers=UA,timeout=25);r.raise_for_status();return parse_repo(r.text,RBI)

def build():
    cpi=fetch_release('cpi',parse_cpi);iip=fetch_release('iip',parse_iip);repo=fetch_repo()
    if any(x.get('status')!='live' or not finite(x.get('value')) for x in (cpi,iip,repo)):
        raise RuntimeError('India domestic macro source is stale or unavailable')
    inflation_gap=float(cpi['value'])-4.0
    real_repo=float(repo['value'])-float(cpi['value'])
    inflation_score=float(np.tanh(-inflation_gap/1.5))
    activity_score=float(np.tanh((float(iip['value'])-5.0)/4.0))
    policy_score=float(np.tanh(-(real_repo-1.0)/1.5))
    score=.40*inflation_score+.35*activity_score+.25*policy_score
    factors={
      'india_cpi_yoy':dict(cpi,score=inflation_score,reference=4.0,reference_label='RBI inflation target'),
      'india_iip_yoy':dict(iip,score=activity_score,reference=5.0,reference_label='medium-growth anchor'),
      'india_repo_rate':dict(repo,score=policy_score,real_repo=real_repo,reference_real_rate=1.0,reference_label='real policy-rate anchor')
    }
    return {'score':float(score),'coverage':1.0,'status':'live','factors':factors,'inflation_gap_pp':inflation_gap,'real_repo_rate':real_repo,'method':'economic-anchor-v1'}
