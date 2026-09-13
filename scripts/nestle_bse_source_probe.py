#!/usr/bin/env python3
"""Diagnostic-only probe of BSE's official corporate-announcement API for Nestle India.

This does not change source eligibility, does not fetch any NIFTY valuation
target, and has zero live authority. It exists only to freeze the real BSE JSON
schema and locate pre-NSE-listing official filings for scrip 500790.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "nestle_bse_source_probe.json"
API = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
REFERER = "https://www.bseindia.com/corporates/ann.html"
UA = "Mozilla/5.0 (compatible; AnupNiftyValuation/BSE-source-probe-v1; personal non-commercial research)"


def get_page(session: requests.Session, page: int) -> dict:
    params = {
        "pageno": page,
        "strCat": "-1",
        "subcategory": "-1",
        "strPrevDate": "20220701",
        "strToDate": "20230801",
        "strSearch": "P",
        "strscrip": "500790",
        "strType": "C",
    }
    r = session.get(
        API, params=params, timeout=30,
        headers={
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.bseindia.com",
            "Referer": REFERER,
        },
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise ValueError("BSE API response is not an object")
    return data


def build() -> dict:
    s = requests.Session()
    rows = []
    pages = []
    total_hint = None
    for page in range(1, 21):
        data = get_page(s, page)
        table = data.get("Table") or []
        table1 = data.get("Table1") or []
        if table1 and isinstance(table1[0], dict):
            for key in ("ROWCNT", "RowCnt", "rowcnt"):
                if key in table1[0]:
                    try:
                        total_hint = int(table1[0][key])
                    except Exception:
                        pass
        pages.append({
            "page": page,
            "rows": len(table) if isinstance(table, list) else None,
            "top_level_keys": sorted(data.keys()),
            "table1_sample": table1[:1] if isinstance(table1, list) else None,
        })
        if not isinstance(table, list) or not table:
            break
        rows.extend(table)
        if total_hint is not None and len(rows) >= total_hint:
            break
        time.sleep(0.12)

    keys = sorted({str(k) for row in rows if isinstance(row, dict) for k in row.keys()})
    compact = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        # Preserve the full raw row because this is a schema probe and the
        # official endpoint is the evidence. No eligibility decision is made.
        compact.append(row)

    result = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "research_only": True,
        "live_authority": "none",
        "holdout_target_fetch_count": 0,
        "source": {
            "api": API,
            "referer": REFERER,
            "scrip_code": "500790",
            "from": "2022-07-01",
            "to": "2023-08-01",
        },
        "row_count": len(compact),
        "total_hint": total_hint,
        "row_keys": keys,
        "pages": pages,
        "rows": compact,
        "guardrail": "Diagnostic BSE schema/source inventory only. No filing becomes eligible here and no NIFTY valuation target is requested.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "row_count": result["row_count"],
        "total_hint": total_hint,
        "row_keys": keys,
        "pages": pages,
    }, indent=2))
    return result


if __name__ == "__main__":
    build()
