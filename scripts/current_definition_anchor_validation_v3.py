#!/usr/bin/env python3
"""Anchor validation v3: legacy context recovery + throttle-safe NSE archive fetches."""
from __future__ import annotations
import threading,time
import xml.etree.ElementTree as ET
import requests

import current_definition_anchor_validation_v2 as v2

a=v2.a
_LOCK=threading.Lock()
_LAST=[0.0]


def _candidates(url):
    out=[url]
    if url.endswith('.xml') and not url.endswith('_WEB.xml'):
        out.append(url[:-4]+'_WEB.xml')
    if url.endswith('_WEB.xml'):
        out.append(url.replace('_WEB.xml','.xml'))
    return list(dict.fromkeys(out))


def xbrl_root(url):
    last=None
    for candidate in _candidates(url):
        for attempt in range(6):
            try:
                with _LOCK:
                    gap=time.monotonic()-_LAST[0]
                    if gap<0.55:time.sleep(0.55-gap)
                    headers={**a.UA,'Accept':'application/xml,text/xml,*/*','Referer':'https://www.nseindia.com/companies-listing/corporate-filings-financial-results'}
                    r=a.sess().get(candidate,headers=headers,timeout=35)
                    _LAST[0]=time.monotonic()
                if r.status_code==403:
                    # Refresh cookies and back off; do not treat throttling as missing data.
                    try:a.sess().get('https://www.nseindia.com/',headers=a.UA,timeout=15)
                    except Exception:pass
                    time.sleep(1.5*(attempt+1));continue
                if r.status_code==404:
                    last=requests.HTTPError(f'404 for {candidate}');break
                r.raise_for_status()
                return ET.fromstring(r.content)
            except Exception as e:
                last=e
                if attempt<5:time.sleep(0.8*(attempt+1))
    raise last or RuntimeError('xbrl unavailable')

a.xbrl_root=xbrl_root

if __name__=='__main__':
    a.main()
