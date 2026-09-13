#!/usr/bin/env python3
"""Resolve the five residual development-source gaps using official NSE evidence only.

Research only; zero live authority. This stage deliberately does not fetch any
holdout NIFTY valuation target. It resolves historical company identity changes,
life-insurance filing routes, and Nestle India's calendar-year annual source.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import re
import time
from urllib.parse import urlparse

import pandas as pd
import requests

import development_accounting_source_map as base

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "development_residual_source_policy_v1.json").read_text(encoding="utf-8"))
OUT = ROOT / "data" / "development_residual_source_resolution.json"
ANN_PAGE = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"
ANN_API = "https://www.nseindia.com/api/corporate-announcements"

ALIASES = {
    old: spec["current_symbol"] for old, spec in POLICY["identity_aliases"].items()
}
RESIDUAL = list(POLICY["residual_symbols"])
LIFE = set(POLICY["life_insurance_symbols"])

QUARTER_ENDS = {(3, 31), (6, 30), (9, 30), (12, 31)}
MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def _session() -> requests.Session:
    return base._session()


def _announcement_timestamp(r: dict) -> pd.Timestamp | None:
    for key in ("exchdisstime", "an_dt", "dt"):
        v = r.get(key)
        if v in (None, ""):
            continue
        d = pd.to_datetime(v, errors="coerce", dayfirst=True)
        if not pd.isna(d):
            if d.tzinfo is not None:
                d = d.tz_convert(None)
            return d
    return None


def _financial_result_like(r: dict) -> bool:
    text = " ".join(str(r.get(k) or "") for k in ("desc", "attchmntText")).lower()
    return "financial result" in text or ("outcome" in text and "result" in text)


def _official_attachment_url(r: dict) -> str | None:
    u = str(r.get("attchmntFile") or "").strip()
    if not u:
        return None
    p = urlparse(u)
    if p.scheme != "https" or p.hostname != "nsearchives.nseindia.com":
        return None
    return u


def fetch_announcements(session: requests.Session, symbol: str) -> dict:
    start = pd.Timestamp(POLICY["announcement_fallback"]["start_date"])
    end = pd.Timestamp(POLICY["announcement_fallback"]["end_date"])
    chunk = int(POLICY["announcement_fallback"]["chunk_days"])
    rows: list[dict] = []
    attempts = []
    cur = start
    while cur <= end:
        stop = min(cur + pd.Timedelta(days=chunk - 1), end)
        params = {
            "index": "equities",
            "symbol": symbol,
            "from_date": cur.strftime("%d-%m-%Y"),
            "to_date": stop.strftime("%d-%m-%Y"),
        }
        try:
            got = base._get_json(session, ANN_API, params, referer=ANN_PAGE)
            attempts.append({"from": str(cur.date()), "to": str(stop.date()), "status": "ok", "records": len(got)})
            rows.extend(got)
        except Exception as e:
            attempts.append({"from": str(cur.date()), "to": str(stop.date()), "status": "unavailable", "error": f"{type(e).__name__}: {e}"})
        cur = stop + pd.Timedelta(days=1)
        time.sleep(0.08)
    return {"symbol": symbol, "records": base._dedupe(rows), "attempts": attempts}


def _download_pdf(session: requests.Session, url: str) -> bytes:
    if urlparse(url).hostname != "nsearchives.nseindia.com":
        raise ValueError("non-NSE archive attachment refused")
    r = session.get(url, timeout=35, headers={**base.UA, "Referer": ANN_PAGE})
    r.raise_for_status()
    raw = r.content
    if len(raw) < 1000 or not raw.lstrip().startswith(b"%PDF"):
        raise ValueError("attachment is not a plausible PDF")
    return raw


def _parse_date_token(token: str) -> pd.Timestamp | None:
    x = re.sub(r"(?i)(\d)(st|nd|rd|th)\b", r"\1", token.strip())
    x = re.sub(r"\s+", " ", x)
    d = pd.to_datetime(x, errors="coerce", dayfirst=True)
    if pd.isna(d):
        return None
    if d.tzinfo is not None:
        d = d.tz_convert(None)
    return d.normalize()


def extract_quarter_end_dates(text: str, public_ts: pd.Timestamp) -> list[pd.Timestamp]:
    """Extract plausible quarter ends from the first portion of an official result PDF."""
    head = text[:20000]
    tokens = []
    month_words = "Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
    tokens.extend(re.findall(rf"\b\d{{1,2}}(?:st|nd|rd|th)?[\s./-]+(?:{month_words})[\s,./-]+\d{{2,4}}\b", head, flags=re.I))
    tokens.extend(re.findall(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", head))
    out = set()
    for token in tokens:
        d = _parse_date_token(token)
        if d is None:
            continue
        if (d.month, d.day) not in QUARTER_ENDS:
            continue
        age = (public_ts.normalize() - d).days
        if 0 <= age <= 500:
            out.add(d)
    return sorted(out)


def current_period_end_from_pdf(text: str, public_ts: pd.Timestamp) -> pd.Timestamp | None:
    candidates = extract_quarter_end_dates(text, public_ts)
    recent = [d for d in candidates if 0 <= (public_ts.normalize() - d).days <= 120]
    return max(recent) if recent else None


def _audited_indicator(text: str) -> bool:
    head = text[:12000].upper().replace("UNAUDITED", "")
    return bool(re.search(r"\bAUDITED\b", head))


def _consolidated_indicator(text: str) -> bool:
    return "CONSOLIDATED" in text[:12000].upper()


def announcement_result_sources(session: requests.Session, symbol: str) -> dict:
    fetched = fetch_announcements(session, symbol)
    parsed = []
    for r in fetched["records"]:
        if not _financial_result_like(r):
            continue
        u = _official_attachment_url(r)
        ts = _announcement_timestamp(r)
        if not u or ts is None or not u.lower().split("?")[0].endswith(".pdf"):
            continue
        try:
            raw = _download_pdf(session, u)
            text = base.pilot.pdf_to_text(raw)
            pe = current_period_end_from_pdf(text, ts)
            if pe is None:
                continue
            parsed.append({
                "symbol": symbol,
                "queried_symbol": symbol,
                "source_kind": "official_nse_announcement_pdf",
                "public_timestamp": ts.isoformat(),
                "period_end": str(pe.date()),
                "consolidated_available": _consolidated_indicator(text),
                "audited_indicator": _audited_indicator(text),
                "attachment_url": u,
                "description": r.get("desc"),
                "attachment_text": r.get("attchmntText"),
            })
        except Exception:
            continue
    # Prefer later dissemination when duplicate result packets exist.
    by_period = {}
    for r in parsed:
        key = (r["period_end"], bool(r["consolidated_available"]))
        old = by_period.get(key)
        if old is None or pd.Timestamp(r["public_timestamp"]) > pd.Timestamp(old["public_timestamp"]):
            by_period[key] = r
    return {"symbol": symbol, "attempts": fetched["attempts"], "sources": list(by_period.values())}


def _annotate_query(records: list[dict], queried_symbol: str) -> list[dict]:
    out = []
    for r in records:
        x = dict(r)
        x["_queried_symbol"] = queried_symbol
        out.append(x)
    return out


def structured_sources(session: requests.Session, original_symbol: str) -> dict:
    symbols = [original_symbol]
    if original_symbol in ALIASES:
        symbols.append(ALIASES[original_symbol])
    q: list[dict] = []
    a: list[dict] = []
    attempts = []
    for sym in symbols:
        qr = base.fetch_financial(session, sym, "Quarterly")
        ar = base.fetch_financial(session, sym, "Annual")
        q.extend(_annotate_query(qr["records"], sym))
        a.extend(_annotate_query(ar["records"], sym))
        attempts.append({"queried_symbol": sym, "quarterly": qr["attempts"], "annual": ar["attempts"], "quarterly_records": len(qr["records"]), "annual_records": len(ar["records"])})
    return {"quarterly": base._dedupe(q), "annual": base._dedupe(a), "attempts": attempts}


def _compact_with_query(r: dict) -> dict:
    x = base.compact_record(r)
    x["queried_symbol"] = r.get("_queried_symbol") or r.get("symbol")
    x["source_kind"] = "structured_financial_results_api"
    return x


def reporting_chain(records: list[dict], signal_date: str, need: int = 4) -> dict:
    cutoff = pd.Timestamp(signal_date) + pd.Timedelta(hours=15, minutes=30)
    eligible = []
    for r in records:
        ts, _ = base.public_timestamp(r)
        pe = base.period_end(r)
        if ts is None or pe is None or ts > cutoff:
            continue
        eligible.append(r)
    periods = sorted({base.period_end(r) for r in eligible}, reverse=True)
    chosen = []
    for pe in periods[:need]:
        same = [r for r in eligible if base.period_end(r) == pe]
        cons = [r for r in same if "consolidated" in str(r.get("consolidated", "")).lower()]
        use = cons or same
        if use:
            chosen.append(_compact_with_query(max(use, key=lambda r: base.public_timestamp(r)[0])))
    return {"complete": len(chosen) >= need, "periods_found": len(chosen), "records": chosen}


def nestle_calendar_annual(records: list[dict], signal_date: str) -> dict:
    cutoff = pd.Timestamp(signal_date) + pd.Timedelta(hours=15, minutes=30)
    candidates = []
    for r in records:
        ts, _ = base.public_timestamp(r)
        pe = base.period_end(r)
        audit = str(r.get("audited") or "").strip().lower()
        if ts is None or pe is None or ts > cutoff:
            continue
        if (pe.month, pe.day) != (12, 31) or audit != "audited":
            continue
        candidates.append(r)
    if not candidates:
        return {"complete": False, "record": None}
    latest_pe = max(base.period_end(r) for r in candidates)
    same = [r for r in candidates if base.period_end(r) == latest_pe]
    cons = [r for r in same if "consolidated" in str(r.get("consolidated", "")).lower()]
    best = max(cons or same, key=lambda r: base.public_timestamp(r)[0])
    return {"complete": True, "record": _compact_with_query(best), "rule": "audited_31_dec_calendar_year"}


def announcement_chain(sources: list[dict], signal_date: str, need: int = 4) -> dict:
    cutoff = pd.Timestamp(signal_date) + pd.Timedelta(hours=15, minutes=30)
    eligible = [r for r in sources if pd.Timestamp(r["public_timestamp"]) <= cutoff]
    periods = sorted({pd.Timestamp(r["period_end"]) for r in eligible}, reverse=True)
    chosen = []
    for pe in periods[:need]:
        same = [r for r in eligible if pd.Timestamp(r["period_end"]) == pe]
        cons = [r for r in same if r["consolidated_available"]]
        if same:
            chosen.append(max(cons or same, key=lambda r: pd.Timestamp(r["public_timestamp"])))
    return {"complete": len(chosen) >= need, "periods_found": len(chosen), "records": chosen}


def announcement_annual(sources: list[dict], signal_date: str, symbol: str) -> dict:
    cutoff = pd.Timestamp(signal_date) + pd.Timedelta(hours=15, minutes=30)
    year_end = (12, 31) if symbol == "NESTLEIND" else (3, 31)
    eligible = [
        r for r in sources
        if pd.Timestamp(r["public_timestamp"]) <= cutoff
        and (pd.Timestamp(r["period_end"]).month, pd.Timestamp(r["period_end"]).day) == year_end
        and r["audited_indicator"]
    ]
    if not eligible:
        return {"complete": False, "record": None}
    latest = max(pd.Timestamp(r["period_end"]) for r in eligible)
    same = [r for r in eligible if pd.Timestamp(r["period_end"]) == latest]
    cons = [r for r in same if r["consolidated_available"]]
    return {"complete": True, "record": max(cons or same, key=lambda r: pd.Timestamp(r["public_timestamp"]))}


def build() -> dict:
    session = _session()
    snapshots = base._development_snapshots(session)
    residual_by_month = {s["month"]: [r["symbol"] for r in s["constituents"] if r["symbol"] in RESIDUAL] for s in snapshots}

    structured = {sym: structured_sources(session, sym) for sym in RESIDUAL}
    announcements = {sym: announcement_result_sources(session, sym) for sym in RESIDUAL}

    month_results = []
    resolved = 0
    unresolved = []
    method_counts: dict[str, int] = {}
    for snap in snapshots:
        month = snap["month"]
        signal = snap["signal_date"]
        rows = []
        for sym in residual_by_month[month]:
            ss = structured[sym]
            ttm = reporting_chain(ss["quarterly"], signal, 4)
            annual_raw = base.pick_annual(ss["annual"], signal)
            annual = {
                "complete": annual_raw.get("complete", False),
                "record": annual_raw.get("record"),
                "method": "structured_annual_api" if annual_raw.get("complete") else None,
            }
            ttm_method = "structured_financial_results_api" if ttm["complete"] else None

            if sym == "NESTLEIND" and not annual["complete"]:
                n = nestle_calendar_annual(ss["quarterly"], signal)
                if n["complete"]:
                    annual = {"complete": True, "record": n["record"], "method": "nestle_audited_31_dec_quarterly_record"}

            if not ttm["complete"]:
                ac = announcement_chain(announcements[sym]["sources"], signal, 4)
                if ac["complete"]:
                    ttm = ac
                    ttm_method = "official_announcement_pdf"
            if not annual["complete"]:
                aa = announcement_annual(announcements[sym]["sources"], signal, sym)
                if aa["complete"]:
                    annual = {"complete": True, "record": aa["record"], "method": "official_announcement_pdf"}

            complete = bool(ttm["complete"] and annual["complete"])
            if complete:
                resolved += 1
                for m in (ttm_method, annual["method"]):
                    if m:
                        method_counts[m] = method_counts.get(m, 0) + 1
            else:
                unresolved.append({"month": month, "symbol": sym, "ttm_complete": bool(ttm["complete"]), "annual_complete": bool(annual["complete"])})
            rows.append({
                "symbol": sym,
                "complete": complete,
                "ttm_method": ttm_method,
                "ttm_source_chain": ttm,
                "annual_method": annual["method"],
                "annual_source": annual,
            })
        month_results.append({"month": month, "signal_date": signal, "residuals": rows})

    result = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "research_only": True,
        "live_authority": "none",
        "live_model_changed": False,
        "live_allocation_changed": False,
        "policy_id": POLICY["policy_id"],
        "baseline_complete_company_months": 270,
        "baseline_total_company_months": 300,
        "residual_company_months": 30,
        "resolved_residual_company_months": resolved,
        "combined_complete_company_months": 270 + resolved,
        "unresolved": unresolved,
        "method_counts": method_counts,
        "identity_aliases": POLICY["identity_aliases"],
        "source_attempts": {
            sym: {
                "structured": structured[sym]["attempts"],
                "announcement_attempts": announcements[sym]["attempts"],
                "announcement_sources_parsed": len(announcements[sym]["sources"]),
            } for sym in RESIDUAL
        },
        "months": month_results,
        "holdout_target_fetch_count": 0,
        "interpretation_guardrail": "This resolves filing-source identity only. It does not yet parse constituent profit, net worth, share capital or dividends and therefore does not reproduce or validate a NIFTY valuation ratio.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "resolved_residual_company_months": resolved,
        "combined_complete_company_months": 270 + resolved,
        "unresolved": len(unresolved),
        "announcement_sources": {s: len(announcements[s]["sources"]) for s in RESIDUAL},
        "holdout_target_fetch_count": 0,
    }, indent=2))
    return result


if __name__ == "__main__":
    build()
