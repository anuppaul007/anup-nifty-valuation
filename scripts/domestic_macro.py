"""India domestic macro block for Anup Nifty Valuation V3.6.

Primary current data source: the National Statistical Office's official
``mospi-esankhyiki`` client/API. MoSPI release PDFs remain a fallback.
RBI is used for the current policy repo rate.

Scores use explicit economic anchors rather than pretending that rebased series
have one perfectly stable historical z-score: 4% CPI, 5% IIP growth and a 1%
real policy-rate reference.
"""
from __future__ import annotations
from contextlib import redirect_stdout
from datetime import date
from io import BytesIO,StringIO
from urllib.parse import urljoin
import math,re
import numpy as np
import pandas as pd
from lxml import html
from pypdf import PdfReader
import http_client as requests

UA={'User-Agent':'Mozilla/5.0 (compatible; AnupNiftyValuation/3.6; personal research)'}
MOSPI='https://www.mospi.gov.in/'
MOSPI_ARCHIVE='https://www.mospi.gov.in/archive/press-release'
RBI='https://www.rbi.org.in/'
ESANKHYIKI='https://api.mospi.gov.in/'


def finite(x):
    try:return x is not None and math.isfinite(float(x))
    except (TypeError,ValueError):return False

def fresh(asof,max_age):
    try:
        age=(date.today()-date.fromisoformat(str(asof)[:10])).days
        return 0<=age<=max_age
    except (TypeError,ValueError):return False

def period_end(month,year):
    if isinstance(month,(int,float,np.integer,np.floating)) or str(month).strip().isdigit():
        mm=int(float(month))
    else:mm=pd.to_datetime(str(month).strip(),format='%B').month
    return pd.Period(f'{int(year):04d}-{mm:02d}',freq='M').end_time.date().isoformat()

def clean_text(text):
    if '<' in str(text)[:200]:
        try:return ' '.join(html.fromstring(text).text_content().split())
        except Exception:pass
    return ' '.join(str(text).split())

def release_text(response):
    content=getattr(response,'content',b'') or b''
    if content[:5]==b'%PDF-':
        reader=PdfReader(BytesIO(content));return ' '.join(' '.join((p.extract_text() or '').split()) for p in reader.pages)
    return clean_text(response.text)

def norm(s):return re.sub(r'[^a-z0-9]','',str(s).lower())
def fnum(x):
    try:
        if x is None or str(x).strip() in ('','-','nan','None'):return None
        v=float(str(x).replace(',','').replace('%','').strip());return v if math.isfinite(v) else None
    except Exception:return None

def records(result):
    """Flatten common MoSPI API response shapes without depending on internals."""
    if isinstance(result,list):return [x for x in result if isinstance(x,dict)]
    if not isinstance(result,dict):return []
    data=result.get('data',result)
    if isinstance(data,list):return [x for x in data if isinstance(x,dict)]
    if isinstance(data,dict):
        for key in ('data','indicator','records','result'):
            if isinstance(data.get(key),list):return [x for x in data[key] if isinstance(x,dict)]
    return []

def row_value(row,aliases):
    d={norm(k):v for k,v in row.items()}
    for a in aliases:
        if norm(a) in d:return d[norm(a)]
    return None

def month_number(value):
    if value is None:return None
    s=str(value).strip()
    try:
        if s.isdigit():
            m=int(s);return m if 1<=m<=12 else None
        return pd.to_datetime(s,format='%B').month
    except Exception:
        try:return pd.to_datetime(s,format='%b').month
        except Exception:return None

def _is_all_india_combined(row):
    values=' '.join(str(v).lower() for v in row.values())
    state=row_value(row,['state','state_name','state_description','state_desc'])
    sector=row_value(row,['sector','sector_name','sector_description','sector_desc'])
    state_code=row_value(row,['state_code','statecode']);sector_code=row_value(row,['sector_code','sectorcode'])
    state_ok=(state is not None and 'all india' in str(state).lower()) or str(state_code).strip()=='99' or 'all india' in values
    sector_ok=(sector is not None and 'combined' in str(sector).lower()) or str(sector_code).strip()=='3' or 'combined' in values
    return state_ok and sector_ok

def _is_general(row):
    class_keys=('group','subgroup','division','class','subclass','category','subcategory','description','item')
    parts=[]
    for k,v in row.items():
        if any(x in norm(k) for x in class_keys):parts.append(str(v).lower())
    text=' '.join(parts)
    return any(x in text for x in ('general','all items','overall'))

def _latest_row(rows,require_general=True):
    candidates=[]
    for row in rows:
        if not _is_all_india_combined(row):continue
        if require_general and not _is_general(row):continue
        y=fnum(row_value(row,['year','calendar_year']));mo=month_number(row_value(row,['month','month_name','month_code']))
        if y is None or mo is None:continue
        candidates.append((int(y),mo,row))
    if not candidates and require_general:return _latest_row(rows,False)
    return max(candidates,key=lambda x:(x[0],x[1])) if candidates else None

def _api_client():
    from esankhyiki.client import MoSPI
    return MoSPI()

def _api_get(dataset,params):
    client=_api_client();sink=StringIO()
    with redirect_stdout(sink):result=client.get_data(dataset,params)
    if isinstance(result,dict) and result.get('error'):raise RuntimeError(result['error'])
    return records(result)

def api_cpi():
    year=date.today().year
    params={'base_year':'2024','series':'Current','year':f'{year-1},{year}','state_code':'99','sector_code':'3','Format':'JSON','limit':5000,'page':1}
    rows=_api_get('CPI_Group',params)
    latest=_latest_row(rows)
    if not latest:raise RuntimeError('Official eSankhyiki CPI rows could not identify All-India Combined General')
    y,mo,row=latest
    inflation=fnum(row_value(row,['inflation','inflation_rate','annual_inflation','yoy_inflation','year_on_year_inflation']))
    if inflation is None:
        idx=fnum(row_value(row,['index','index_value','cpi','cpi_index']))
        prior=None
        for r in rows:
            yy=fnum(row_value(r,['year','calendar_year']));mm=month_number(row_value(r,['month','month_name','month_code']))
            if yy==y-1 and mm==mo and _is_all_india_combined(r) and (not _is_general(row) or _is_general(r)):
                prior=fnum(row_value(r,['index','index_value','cpi','cpi_index']));break
        if idx is not None and prior not in (None,0):inflation=100*(idx/prior-1)
    if inflation is None or not -5<inflation<30:raise RuntimeError('Official eSankhyiki CPI inflation missing or invalid')
    asof=period_end(mo,y)
    return {'value':float(inflation),'asof':asof,'source_url':ESANKHYIKI,'status':'live' if fresh(asof,75) else 'stale','label':'All-India CPI inflation, YoY','source':'MoSPI eSankhyiki CPI 2024=100'}

def api_iip():
    year=date.today().year
    params={'base_year':'2022-23','year':f'{year-1},{year}','type':'All','Format':'JSON','limit':5000,'page':1}
    rows=_api_get('IIP_Monthly',params)
    # IIP is all-India by construction; choose the General/overall monthly row.
    candidates=[]
    for row in rows:
        if not _is_general(row):continue
        y=fnum(row_value(row,['year','calendar_year']));mo=month_number(row_value(row,['month','month_name','month_code']))
        if y is not None and mo is not None:candidates.append((int(y),mo,row))
    if not candidates:
        for row in rows:
            y=fnum(row_value(row,['year','calendar_year']));mo=month_number(row_value(row,['month','month_name','month_code']))
            typ=' '.join(str(v).lower() for v in row.values())
            if y is not None and mo is not None and ('general' in typ or 'overall' in typ):candidates.append((int(y),mo,row))
    if not candidates:raise RuntimeError('Official eSankhyiki IIP rows could not identify General monthly index')
    y,mo,row=max(candidates,key=lambda x:(x[0],x[1]))
    growth=fnum(row_value(row,['growth','growth_rate','growthrate','yoy_growth','annual_growth']))
    if growth is None:
        idx=fnum(row_value(row,['index','index_value','iip','iip_index']))
        prior=None
        for yy,mm,r in candidates:
            if yy==y-1 and mm==mo:
                prior=fnum(row_value(r,['index','index_value','iip','iip_index']));break
        if idx is not None and prior not in (None,0):growth=100*(idx/prior-1)
    if growth is None or not -30<growth<40:raise RuntimeError('Official eSankhyiki IIP growth missing or invalid')
    asof=period_end(mo,y)
    return {'value':float(growth),'asof':asof,'source_url':ESANKHYIKI,'status':'live' if fresh(asof,90) else 'stale','label':'India IIP growth, YoY','source':'MoSPI eSankhyiki IIP 2022-23=100'}

def _release_match(kind,title,href):
    s=(title+' '+href).lower().replace('_',' ').replace('-',' ')
    return ('cpi' in s or 'consumer price index' in s) if kind=='cpi' else ('iip' in s or 'industrial production' in s)

def _candidates_from_page(url):
    r=requests.get(url,headers=UA,timeout=25);r.raise_for_status();tree=html.fromstring(r.text);out=[]
    for a in tree.xpath('//a[@href]'):
        href=urljoin(url,a.get('href') or '');own=' '.join(a.text_content().split());parent=' '.join(a.getparent().text_content().split()) if a.getparent() is not None else ''
        title=own if len(own)>8 and own.lower() not in ('read more','view document','view more') else parent;out.append((title,href))
    return out

def discover_release(kind):
    pages=[MOSPI]+[f'{MOSPI_ARCHIVE}?field_press_release_category_tid=All&order=field_release_date&sort=desc&page={p}' for p in range(0,4)]
    for page in pages:
        try:candidates=_candidates_from_page(page)
        except Exception:continue
        for title,href in candidates:
            if _release_match(kind,title,href):
                context=(title+' '+href).lower()
                if any(x in context for x in ('press','release','latestrelease','quick estimate','uploads/')):return title,href
    raise RuntimeError(f'MoSPI {kind.upper()} release link not found')

def parse_cpi(text,source_url=None):
    page=clean_text(text);pats=[r'Retail inflation based on Consumer Price Index in\s+([A-Za-z]+),?\s+(\d{4})\s+is\s+(-?\d+(?:\.\d+)?)\s*%',r'Year[- ]on[- ]year inflation rate based on All India Consumer Price Index.*?(?:month of|for)\s+([A-Za-z]+),?\s+(\d{4}).{0,260}?(?:is|stood at)\s+(-?\d+(?:\.\d+)?)\s*%']
    match=None
    for p in pats:
        match=re.search(p,page,re.I)
        if match:break
    if not match:raise RuntimeError('All-India CPI inflation not parsed')
    month,year,value=match.groups();value=float(value)
    if not -5<value<30:raise RuntimeError('CPI inflation outside validation range')
    asof=period_end(month,year);return {'value':value,'asof':asof,'source_url':source_url,'status':'live' if fresh(asof,75) else 'stale','label':'All-India CPI inflation, YoY'}

def parse_iip(text,source_url=None):
    page=clean_text(text);p1=r'IIP growth rate for the month of\s+([A-Za-z]+)\s+(\d{4})\s+is\s+(-?\d+(?:\.\d+)?)\s*(?:percent|%)';p2=r'Index of Industrial Production.*?(?:growth of|grew by)\s+(-?\d+(?:\.\d+)?)\s*%\s+(?:in|during)\s+([A-Za-z]+)\s+(\d{4})'
    m=re.search(p1,page,re.I)
    if m:month,year,value=m.groups()
    else:
        m=re.search(p2,page,re.I)
        if not m:raise RuntimeError('India IIP growth not parsed')
        value,month,year=m.groups()
    value=float(value)
    if not -30<value<40:raise RuntimeError('IIP growth outside validation range')
    asof=period_end(month,year);return {'value':value,'asof':asof,'source_url':source_url,'status':'live' if fresh(asof,90) else 'stale','label':'India IIP growth, YoY'}

def fetch_release(kind,parser):
    _,url=discover_release(kind);r=requests.get(url,headers=UA,timeout=25);r.raise_for_status();return parser(release_text(r),url)

def parse_repo(text,source_url=RBI):
    page=clean_text(text);section=re.search(r'Policy\s+Rates(.*?)(?:Reserve\s+Ratios|Exchange\s+Rates)',page,re.I);target=section.group(1) if section else page
    m=re.search(r'Policy\s+Repo\s+Rate\s*:?\s*(\d+(?:\.\d+)?)\s*%',target,re.I)
    if not m:raise RuntimeError('RBI policy repo rate not parsed')
    value=float(m.group(1))
    if not 1<value<15:raise RuntimeError('Repo rate outside validation range')
    return {'value':value,'asof':date.today().isoformat(),'source_url':source_url,'status':'live','label':'RBI policy repo rate','date_basis':'retrieval date; current policy rate remains effective until changed'}

def fetch_repo():
    r=requests.get(RBI,headers=UA,timeout=25);r.raise_for_status();return parse_repo(r.text,RBI)

def build():
    try:cpi=api_cpi()
    except Exception:cpi=fetch_release('cpi',parse_cpi)
    try:iip=api_iip()
    except Exception:iip=fetch_release('iip',parse_iip)
    repo=fetch_repo()
    if any(x.get('status')!='live' or not finite(x.get('value')) for x in (cpi,iip,repo)):raise RuntimeError('India domestic macro source is stale or unavailable')
    inflation_gap=float(cpi['value'])-4.0;real_repo=float(repo['value'])-float(cpi['value'])
    inflation_score=float(np.tanh(-inflation_gap/1.5));activity_score=float(np.tanh((float(iip['value'])-5.0)/4.0));policy_score=float(np.tanh(-(real_repo-1.0)/1.5))
    score=.40*inflation_score+.35*activity_score+.25*policy_score
    factors={'india_cpi_yoy':dict(cpi,score=inflation_score,reference=4.0,reference_label='RBI inflation target'),'india_iip_yoy':dict(iip,score=activity_score,reference=5.0,reference_label='medium-growth anchor'),'india_repo_rate':dict(repo,score=policy_score,real_repo=real_repo,reference_real_rate=1.0,reference_label='real policy-rate anchor')}
    return {'score':float(score),'coverage':1.0,'status':'live','factors':factors,'inflation_gap_pp':inflation_gap,'real_repo_rate':real_repo,'method':'economic-anchor-v1'}
