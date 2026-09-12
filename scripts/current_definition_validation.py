#!/usr/bin/env python3
"""Pilot inspector for current-definition NIFTY reconstruction.

Research-only. Downloads one official NIFTY 50 monthly weight PDF, inspects its
text structure, samples NSE financial-result records/XBRL links, and requests an
explicit historical corporate-action window. The output is a schema/evidence
artifact used to build the production parser; it does not change model inputs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import json, re, zipfile

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


def inspect_weight_pdf(s):
    url="https://www.niftyindices.com/Indices_-_Market_Capitalisation_and_Weightage/indices_dataSep2023.zip"
    r=s.get(url,timeout=30,headers={**UA,"Referer":"https://www.niftyindices.com/reports/monthly-reports"}); r.raise_for_status()
    z=zipfile.ZipFile(BytesIO(r.content))
    names=z.namelist(); target=next(n for n in names if re.search(r"NIFTY_50_Sep2023\.pdf$",n,re.I))
    pdf=z.read(target); reader=PdfReader(BytesIO(pdf)); text="\n".join((p.extract_text() or "") for p in reader.pages)
    lines=[re.sub(r"\s+"," ",x).strip() for x in text.splitlines() if x.strip()]
    return {"url":url,"file":target,"pages":len(reader.pages),"bytes":len(pdf),"line_count":len(lines),"first_180_lines":lines[:180]}


def inspect_financials(s,symbol):
    data=get_json(s,"https://www.nseindia.com/api/corporates-financial-results",{"index":"equities","symbol":symbol,"period":"Quarterly"})
    rows=data if isinstance(data,list) else data.get("data",[]) if isinstance(data,dict) else []
    out=[]
    for row in rows[:4]:
        clean={k:v for k,v in row.items() if k.lower() not in {"attchmntfile","attchmnttext"}}
        out.append(clean)
    urls=[]
    for row in rows:
        for k,v in row.items():
            if isinstance(v,str) and ("xbrl" in k.lower() or "xbrl" in v.lower() or v.lower().startswith("http")):
                urls.append({"key":k,"value":v})
        if len(urls)>=8: break
    return {"symbol":symbol,"record_count":len(rows),"keys":sorted(rows[0].keys()) if rows else [],"sample_records":out,"url_fields":urls[:8]}


def inspect_xbrl(s, financial_sample):
    candidates=[]
    for uv in financial_sample.get("url_fields",[]):
        v=uv.get("value")
        if isinstance(v,str) and v.lower().startswith("http"):
            candidates.append(v)
    for u in candidates:
        try:
            r=s.get(u,timeout=30,headers=UA); r.raise_for_status()
            txt=r.text
            return {"status":"ok","url":u,"content_type":r.headers.get("content-type"),"chars":len(txt),"head":txt[:5000]}
        except Exception as e:
            last=f"{type(e).__name__}: {e}"
    return {"status":"unavailable","error":locals().get("last","no URL candidate")}


def inspect_actions(s,symbol):
    params={"index":"equities","from_date":"01-09-2022","to_date":"30-09-2023","symbol":symbol}
    data=get_json(s,"https://www.nseindia.com/api/corporates-corporateActions",params)
    rows=data if isinstance(data,list) else data.get("data",[]) if isinstance(data,dict) else []
    return {"symbol":symbol,"params":params,"record_count":len(rows),"keys":sorted(rows[0].keys()) if rows else [],"rows":rows[:25]}


def main():
    s=session(); fin=inspect_financials(s,"RELIANCE")
    out={"generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),"research_only":True,"live_model_changed":False,
         "weight_pdf":inspect_weight_pdf(s),"financials":fin,"xbrl":inspect_xbrl(s,fin),"corporate_actions":inspect_actions(s,"RELIANCE")}
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    print(json.dumps({"weight_lines":out["weight_pdf"]["line_count"],"financial_records":fin["record_count"],"xbrl":out["xbrl"]["status"],"action_records":out["corporate_actions"]["record_count"],"live_model_changed":False}))

if __name__=="__main__": main()
