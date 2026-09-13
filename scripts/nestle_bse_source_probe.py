#!/usr/bin/env python3
"""Diagnostic-only probe of BSE's official corporate-announcement API for Nestle India.

This does not change source eligibility, does not fetch any NIFTY valuation
target, and has zero live authority. It freezes BSE's live JSON schema and
query semantics before the pre-NSE-listing source fallback is implemented.
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
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36"

VARIANTS = [
    {"name": "lower_scrip_minus1", "scrip_key": "strscrip", "subcategory": "-1"},
    {"name": "lower_scrip_empty", "scrip_key": "strscrip", "subcategory": ""},
    {"name": "camel_scrip_minus1", "scrip_key": "strScrip", "subcategory": "-1"},
    {"name": "camel_scrip_empty", "scrip_key": "strScrip", "subcategory": ""},
]
WINDOWS = [
    {"name": "2022H2_2023H1", "from": "20220701", "to": "20230630"},
    {"name": "pre_nse_listing_jul2023", "from": "20230701", "to": "20230801"},
]


def request_page(session: requests.Session, page: int, variant: dict, window: dict) -> tuple[dict, dict]:
    params = {
        "pageno": page,
        "strCat": "-1",
        "subcategory": variant["subcategory"],
        "strPrevDate": window["from"],
        "strToDate": window["to"],
        "strSearch": "P",
        variant["scrip_key"]: "500790",
        "strType": "C",
    }
    r = session.get(
        API,
        params=params,
        timeout=30,
        headers={
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://www.bseindia.com",
            "Referer": REFERER,
        },
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise ValueError("BSE API response is not an object")
    return data, params


def probe_window(session: requests.Session, variant: dict, window: dict) -> dict:
    rows = []
    pages = []
    total_hint = None
    for page in range(1, 21):
        data, params = request_page(session, page, variant, window)
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
            "status": data.get("Status"),
            "message": data.get("Message"),
            "table1_sample": table1[:1] if isinstance(table1, list) else None,
            "params": params,
        })
        if not isinstance(table, list) or not table:
            break
        rows.extend(row for row in table if isinstance(row, dict))
        if total_hint is not None and len(rows) >= total_hint:
            break
        time.sleep(0.12)
    return {
        "window": window,
        "row_count": len(rows),
        "total_hint": total_hint,
        "row_keys": sorted({str(k) for row in rows for k in row.keys()}),
        "pages": pages,
        "rows": rows,
    }


def probe_variant(session: requests.Session, variant: dict) -> dict:
    windows = [probe_window(session, variant, w) for w in WINDOWS]
    rows = []
    seen = set()
    for win in windows:
        for row in win["rows"]:
            key = json.dumps(row, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                rows.append(row)
    return {
        "variant": variant,
        "row_count": len(rows),
        "row_keys": sorted({str(k) for row in rows for k in row.keys()}),
        "windows": windows,
        "rows": rows,
    }


def build() -> dict:
    s = requests.Session()
    results = []
    for variant in VARIANTS:
        results.append(probe_variant(s, variant))
        time.sleep(0.2)
    best = max(results, key=lambda x: x["row_count"])
    result = {
        "schema_version": 3,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "research_only": True,
        "live_authority": "none",
        "holdout_target_fetch_count": 0,
        "source": {
            "api": API,
            "referer": REFERER,
            "scrip_code": "500790",
            "windows": WINDOWS,
        },
        "variants": results,
        "best_variant": best["variant"]["name"],
        "best_row_count": best["row_count"],
        "best_row_keys": best["row_keys"],
        "guardrail": "Diagnostic BSE schema/source inventory only. No filing becomes eligible here and no NIFTY valuation target is requested.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "best_variant": result["best_variant"],
        "best_row_count": result["best_row_count"],
        "best_row_keys": result["best_row_keys"],
        "variants": [
            {
                "name": x["variant"]["name"],
                "row_count": x["row_count"],
                "windows": [
                    {
                        "name": w["window"]["name"],
                        "row_count": w["row_count"],
                        "status": w["pages"][0].get("status") if w["pages"] else None,
                        "message": w["pages"][0].get("message") if w["pages"] else None,
                    } for w in x["windows"]
                ],
            } for x in results
        ],
    }, indent=2))
    return result


if __name__ == "__main__":
    build()
