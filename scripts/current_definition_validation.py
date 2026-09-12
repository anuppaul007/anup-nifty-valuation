#!/usr/bin/env python3
"""Pilot inspector for current-definition NIFTY reconstruction.

Research-only. Decodes the official NIFTY 50 monthly weight PDF and NSE
financial-result/XBRL schemas needed for a production constituent-level
reconstruction. It does not change model inputs or allocations.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import json, re, zipfile
import xml.etree.ElementTree as ET

import pdfplumber
import requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "current_definition_validation.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; AnupNiftyValuation/3.6; personal research)",
      "Accept": "application/json,text/plain,*/*"}


def session():
    s=requests.Session(); s.headers.update(UA)
    for u in ("https://www.nseindia.com/", "https://www.niftyindices.com/"):
        try: s.get(u, timeout=15)
        except Exception: pass
    return s


def get_json(s,url,params=None):
    r=s.get(url,params=params,timeout=30,headers=UA); r.raise_for_status(); return r.json()


def weight_pdf_bytes(s, month="Sep2023"):
    url=f"https://www.niftyindices.com/Indices_-_Market_Capitalisation_and_Weightage/indices_data{month}.zip"
    r=s.get(url,timeout=30,headers={**UA,"Referer":"https://www.niftyindices.com/reports/monthly-reports"}); r.raise_for_status()
    z=zipfile.ZipFile(BytesIO(r.content)); names=z.namelist()
    target=next(n for n in names if re.search(rf"NIFTY_50_{month}\.pdf$",n,re.I))
    return url,target,z.read(target)


def inspect_weight_pdf(s):
    url,target,pdf=weight_pdf_bytes(s)
    reader=PdfReader(BytesIO(pdf)); text="\n".join((p.extract_text() or "") for p in reader.pages)
    lines=[re.sub(r"\s+"," ",x).strip() for x in text.splitlines() if x.strip()]
    tables=[]; words=[]
    with pdfplumber.open(BytesIO(pdf)) as doc:
        for pi,p in enumerate(doc.pages):
            tbl=p.extract_table()
            if tbl: tables.append({"page":pi+1,"rows":tbl[:35]})
            if pi==0:
                words=[{"text":w.get("text"),"x0":round(float(w.get("x0",0)),1),"top":round(float(w.get("top",0)),1)} for w in p.extract_words()[:240]]
    return {"url":url,"file":target,"pages":len(reader.pages),"bytes":len(pdf),"line_count":len(lines),
            "first_90_lines":lines[:90],"pdfplumber_tables":tables,"first_page_words":words}


def financial_rows(s,symbol,period):
    data=get_json(s,"https://www.nseindia.com/api/corporates-financial-results",{"index":"equities","symbol":symbol,"period":period})
    return data if isinstance(data,list) else data.get("data",[]) if isinstance(data,dict) else []


def inspect_financials(s,symbol,period="Quarterly"):
    rows=financial_rows(s,symbol,period)
    cons=[r for r in rows if str(r.get("consolidated","")).lower()=="consolidated"]
    sample=cons[:3] or rows[:3]
    return {"symbol":symbol,"period":period,"record_count":len(rows),"consolidated_count":len(cons),
            "keys":sorted(rows[0].keys()) if rows else [],"sample_records":sample}


def localname(tag): return tag.split("}")[-1].split(":")[-1]


def xbrl_matches(s,url):
    r=s.get(url,timeout=30,headers=UA); r.raise_for_status(); root=ET.fromstring(r.content)
    needles=("profitloss","profit","earningspershare","basic","diluted","networth","networthattributable",
             "equitysharecapital","paidup","facevalue","other equity","otherequity","reserves","numberofshares")
    hits=[]
    for e in root.iter():
        n=localname(e.tag); nl=n.lower().replace("_","").replace("-","")
        if any(k.replace(" ","") in nl for k in needles):
            txt=(e.text or "").strip()
            if txt:
                hits.append({"tag":n,"value":txt,"contextRef":e.attrib.get("contextRef"),"unitRef":e.attrib.get("unitRef"),"decimals":e.attrib.get("decimals")})
    # keep compact but include enough duplicates to see One/Four/current/prior contexts
    return {"url":url,"chars":len(r.content),"match_count":len(hits),"matches":hits[:180]}


def inspect_xbrl_for_period(s,symbol,period):
    rows=financial_rows(s,symbol,period)
    cons=[r for r in rows if str(r.get("consolidated","")).lower()=="consolidated" and isinstance(r.get("xbrl"),str)]
    if not cons: return {"status":"unavailable","symbol":symbol,"period":period}
    row=cons[0]
    try:
        m=xbrl_matches(s,row["xbrl"])
        return {"status":"ok","symbol":symbol,"period":period,"filingDate":row.get("filingDate"),"toDate":row.get("toDate"),"row":row,"xbrl":m}
    except Exception as e:
        return {"status":"unavailable","symbol":symbol,"period":period,"error":f"{type(e).__name__}: {e}","row":row}


def inspect_actions(s,symbol):
    params={"index":"equities","from_date":"01-09-2022","to_date":"30-09-2023","symbol":symbol}
    data=get_json(s,"https://www.nseindia.com/api/corporates-corporateActions",params)
    rows=data if isinstance(data,list) else data.get("data",[]) if isinstance(data,dict) else []
    return {"symbol":symbol,"params":params,"record_count":len(rows),"keys":sorted(rows[0].keys()) if rows else [],"rows":rows[:25]}


def main():
    s=session()
    out={"generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),"research_only":True,"live_model_changed":False,
         "weight_pdf":inspect_weight_pdf(s),
         "reliance_quarterly":inspect_financials(s,"RELIANCE","Quarterly"),
         "reliance_annual":inspect_financials(s,"RELIANCE","Annual"),
         "hdfcbank_quarterly":inspect_financials(s,"HDFCBANK","Quarterly"),
         "hdfcbank_annual":inspect_financials(s,"HDFCBANK","Annual"),
         "reliance_quarterly_xbrl":inspect_xbrl_for_period(s,"RELIANCE","Quarterly"),
         "reliance_annual_xbrl":inspect_xbrl_for_period(s,"RELIANCE","Annual"),
         "hdfcbank_quarterly_xbrl":inspect_xbrl_for_period(s,"HDFCBANK","Quarterly"),
         "hdfcbank_annual_xbrl":inspect_xbrl_for_period(s,"HDFCBANK","Annual"),
         "corporate_actions":inspect_actions(s,"RELIANCE")}
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    print(json.dumps({"weight_tables":len(out["weight_pdf"]["pdfplumber_tables"]),
                      "rel_q_xbrl":out["reliance_quarterly_xbrl"]["status"],"rel_a_xbrl":out["reliance_annual_xbrl"]["status"],
                      "bank_q_xbrl":out["hdfcbank_quarterly_xbrl"]["status"],"bank_a_xbrl":out["hdfcbank_annual_xbrl"]["status"],
                      "live_model_changed":False}))

if __name__=="__main__": main()
