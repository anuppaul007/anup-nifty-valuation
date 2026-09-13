#!/usr/bin/env python3
"""Map point-in-time official accounting sources for the six development months.

Research only; zero live authority. This deliberately does not fetch any of the
30 holdout official NIFTY valuation targets. It identifies the exact filing
metadata and XBRL template coverage needed before numerical reconstruction.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import json
import re
import time
import zipfile

import pandas as pd
import requests

import recent_regime_reconstruction_pilot as pilot

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "recent_reconstruction_policy_v1.json").read_text(encoding="utf-8"))
OUT = ROOT / "data" / "development_accounting_source_map.json"
UA = pilot.UA
DATE_START = "01-04-2021"
DATE_END = "29-02-2024"

FINANCIAL_PAGE = "https://www.nseindia.com/companies-listing/corporate-filings-financial-results"
ACTIONS_PAGE = "https://www.nseindia.com/companies-listing/corporate-filings-actions"


def _bootstrap(session: requests.Session, page: str | None = None) -> None:
    """Refresh NSE anti-bot cookies without treating bootstrap failure as data."""
    try:
        session.cookies.clear()
        session.get("https://www.nseindia.com/", timeout=15, headers=UA)
        if page:
            session.get(page, timeout=15, headers={**UA, "Referer": "https://www.nseindia.com/"})
    except Exception:
        pass


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(UA)
    _bootstrap(s)
    return s


def _records(data) -> list[dict]:
    x = data if isinstance(data, list) else (data.get("data") if isinstance(data, dict) else [])
    return x if isinstance(x, list) else []


def _get_json(session: requests.Session, url: str, params: dict, *, referer: str) -> list[dict]:
    """GET an NSE API endpoint with conservative retry/re-bootstrap.

    Parallel NSE API calls frequently trigger 403s. Source collection is kept
    sequential, and 401/403/429/5xx responses trigger a fresh cookie bootstrap
    plus bounded backoff. A failure remains a recorded source-routing defect.
    """
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            r = session.get(
                url,
                params=params,
                timeout=30,
                headers={**UA, "Accept": "application/json,text/plain,*/*", "Referer": referer},
            )
            r.raise_for_status()
            time.sleep(0.12)
            return _records(r.json())
        except Exception as e:
            last_error = e
            _bootstrap(session, referer)
            time.sleep(0.6 * (attempt + 1))
    assert last_error is not None
    raise last_error


def parse_signal_date(text: str) -> str:
    m = re.search(r"Constituents\s+of\s+NIFTY\s+50\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})", text, flags=re.I | re.S)
    if not m:
        raise ValueError("constituent snapshot date not found")
    return str(pd.to_datetime(m.group(1), errors="raise").date())


def public_timestamp(record: dict) -> tuple[pd.Timestamp | None, str | None]:
    """Use exchange dissemination first, then broadcast, then filing date."""
    for key in ("exchdisstime", "broadCastDate", "filingDate"):
        v = record.get(key)
        if v in (None, ""):
            continue
        d = pd.to_datetime(v, errors="coerce", dayfirst=True)
        if not pd.isna(d):
            if d.tzinfo is not None:
                d = d.tz_convert(None)
            return d, key
    return None, None


def period_end(record: dict) -> pd.Timestamp | None:
    d = pd.to_datetime(record.get("toDate"), errors="coerce", dayfirst=True)
    if pd.isna(d):
        return None
    if d.tzinfo is not None:
        d = d.tz_convert(None)
    return d.normalize()


def template_from_xbrl(url: str | None) -> str | None:
    if not url:
        return None
    upper = str(url).upper()
    for token in ("INDAS", "BANK", "NBFC", "LI", "GI", "INSURANCE"):
        if f"_{token}_" in upper or f"FILING_{token}" in upper:
            return token
    return "OTHER"


def _dedupe(records: list[dict]) -> list[dict]:
    """Deduplicate complete records, including corporate-action schemas."""
    seen = set()
    out = []
    for r in records:
        key = json.dumps(r, sort_keys=True, default=str, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _attempt(session, url, params, label, referer) -> tuple[list[dict], dict]:
    try:
        got = _get_json(session, url, params, referer=referer)
        return got, {"route": label, "status": "ok", "records": len(got)}
    except Exception as e:
        return [], {"route": label, "status": "unavailable", "error": f"{type(e).__name__}: {e}"}


def fetch_financial(session: requests.Session, symbol: str, period: str) -> dict:
    url = "https://www.nseindia.com/api/corporates-financial-results"
    base = {"index": "equities", "symbol": symbol, "period": period}
    attempts = []
    records, attempt = _attempt(session, url, base, "symbol_default", FINANCIAL_PAGE)
    attempts.append(attempt)
    if not records:
        fallback, attempt = _attempt(
            session,
            url,
            {**base, "from_date": DATE_START, "to_date": DATE_END},
            "symbol_explicit_date_window",
            FINANCIAL_PAGE,
        )
        attempts.append(attempt)
        records.extend(fallback)
    return {"symbol": symbol, "period": period, "records": _dedupe(records), "attempts": attempts}


def fetch_actions(session: requests.Session, symbol: str) -> dict:
    url = "https://www.nseindia.com/api/corporates-corporateActions"
    base = {"index": "equities", "symbol": symbol}
    attempts = []
    rows, attempt = _attempt(session, url, base, "symbol_default", ACTIONS_PAGE)
    attempts.append(attempt)
    if not rows:
        fallback, attempt = _attempt(
            session,
            url,
            {**base, "from_date": DATE_START, "to_date": DATE_END},
            "symbol_explicit_date_window",
            ACTIONS_PAGE,
        )
        attempts.append(attempt)
        rows.extend(fallback)
    return {"symbol": symbol, "records": _dedupe(rows), "attempts": attempts}


def compact_record(r: dict) -> dict:
    ts, ts_field = public_timestamp(r)
    pe = period_end(r)
    return {
        "symbol": r.get("symbol"),
        "companyName": r.get("companyName"),
        "period": r.get("period"),
        "relatingTo": r.get("relatingTo"),
        "financialYear": r.get("financialYear"),
        "fromDate": r.get("fromDate"),
        "toDate": r.get("toDate"),
        "period_end": str(pe.date()) if pe is not None else None,
        "public_timestamp": ts.isoformat() if ts is not None else None,
        "public_timestamp_field": ts_field,
        "consolidated": r.get("consolidated"),
        "audited": r.get("audited"),
        "bank": r.get("bank"),
        "format": r.get("format"),
        "indAs": r.get("indAs"),
        "xbrl": r.get("xbrl"),
        "template": template_from_xbrl(r.get("xbrl")),
        "resultDetailedDataLink": r.get("resultDetailedDataLink"),
        "seqNumber": r.get("seqNumber"),
    }


def choose_latest_by_period(records: list[dict], signal_date: str) -> list[dict]:
    cutoff = pd.Timestamp(signal_date) + pd.Timedelta(hours=15, minutes=30)
    eligible = []
    for r in records:
        ts, _ = public_timestamp(r)
        pe = period_end(r)
        if ts is None or pe is None or ts > cutoff:
            continue
        eligible.append(r)
    by_key: dict[tuple, dict] = {}
    for r in eligible:
        pe = period_end(r)
        cons = str(r.get("consolidated", "")).strip().lower()
        key = (pe, "consolidated" if "consolidated" in cons else "standalone")
        old = by_key.get(key)
        if old is None or public_timestamp(r)[0] > public_timestamp(old)[0]:
            by_key[key] = r
    return list(by_key.values())


def pick_reporting_chain(records: list[dict], signal_date: str, need: int = 4) -> dict:
    eligible = choose_latest_by_period(records, signal_date)
    periods = sorted({period_end(r) for r in eligible if period_end(r) is not None}, reverse=True)
    chosen = []
    fallback_periods = []
    for pe in periods[:need]:
        same = [r for r in eligible if period_end(r) == pe]
        consolidated = [r for r in same if "consolidated" in str(r.get("consolidated", "")).lower()]
        use = consolidated or same
        if not use:
            continue
        best = max(use, key=lambda r: public_timestamp(r)[0])
        chosen.append(compact_record(best))
        if not consolidated:
            fallback_periods.append(str(pe.date()))
    return {
        "periods_found": len(chosen),
        "required_periods": need,
        "complete": len(chosen) >= need,
        "standalone_fallback_periods": fallback_periods,
        "records": chosen,
    }


def pick_annual(records: list[dict], signal_date: str) -> dict:
    eligible = choose_latest_by_period(records, signal_date)
    if not eligible:
        return {"complete": False, "record": None}
    periods = sorted({period_end(r) for r in eligible if period_end(r) is not None}, reverse=True)
    for pe in periods:
        same = [r for r in eligible if period_end(r) == pe]
        consolidated = [r for r in same if "consolidated" in str(r.get("consolidated", "")).lower()]
        use = consolidated or same
        if use:
            best = max(use, key=lambda r: public_timestamp(r)[0])
            return {"complete": True, "standalone_fallback": not bool(consolidated), "record": compact_record(best)}
    return {"complete": False, "record": None}


def _development_snapshots(session: requests.Session) -> list[dict]:
    out = []
    for month in POLICY["sample"]["development_months"]:
        raw = pilot._get_bytes(session, pilot.weights_zip_url(month))
        with zipfile.ZipFile(BytesIO(raw)) as z:
            member = pilot._weight_pdf_member(z.namelist(), month)
            pdf = z.read(member)
        text = pilot.pdf_to_text(pdf)
        rows, diag = pilot.parse_weight_table(text)
        if not diag["strict_ok"] or len(rows) != 50:
            raise RuntimeError(f"development weight parse incomplete for {month}: {diag}")
        out.append({"month": month, "signal_date": parse_signal_date(text), "constituents": rows})
    return out


def build() -> dict:
    session = _session()
    snapshots = _development_snapshots(session)
    symbols = sorted({r["symbol"] for s in snapshots for r in s["constituents"]})

    q: dict[str, dict] = {}
    a: dict[str, dict] = {}
    ca: dict[str, dict] = {}
    # Keep the NSE API traversal sequential. Concurrency creates false 403 gaps.
    for idx, sym in enumerate(symbols, start=1):
        if idx > 1 and (idx - 1) % 12 == 0:
            _bootstrap(session)
        q[sym] = fetch_financial(session, sym, "Quarterly")
        a[sym] = fetch_financial(session, sym, "Annual")
        ca[sym] = fetch_actions(session, sym)
        time.sleep(0.12)

    signal_maps = []
    template_counts: dict[str, int] = {}
    gaps = []
    complete_keys = set()
    for snap in snapshots:
        month = snap["month"]
        signal = snap["signal_date"]
        companies = []
        for constituent in snap["constituents"]:
            sym = constituent["symbol"]
            ttm = pick_reporting_chain(q[sym]["records"], signal, 4)
            annual = pick_annual(a[sym]["records"], signal)
            for rec in ttm["records"] + ([annual["record"]] if annual.get("record") else []):
                template = rec.get("template")
                if template:
                    template_counts[template] = template_counts.get(template, 0) + 1
            reason = []
            if not ttm["complete"]:
                reason.append("fewer_than_four_eligible_quarter_ends")
            if not annual["complete"]:
                reason.append("no_eligible_annual_filing")
            if reason:
                gaps.append({"month": month, "symbol": sym, "reasons": reason})
            else:
                complete_keys.add((month, sym))
            companies.append({
                "symbol": sym,
                "weight_pct": constituent["weight_pct"],
                "close_price": constituent["close_price"],
                "index_mcap_crore": constituent["index_mcap_crore"],
                "ttm_source_chain": ttm,
                "annual_book_source": annual,
                "corporate_action_records_available": len(ca[sym]["records"]),
            })
        signal_maps.append({"month": month, "signal_date": signal, "companies": companies})

    per_symbol = []
    for sym in symbols:
        per_symbol.append({
            "symbol": sym,
            "quarterly_records": len(q[sym]["records"]),
            "annual_records": len(a[sym]["records"]),
            "corporate_action_records": len(ca[sym]["records"]),
            "quarterly_attempts": q[sym]["attempts"],
            "annual_attempts": a[sym]["attempts"],
            "corporate_action_attempts": ca[sym]["attempts"],
            "templates": sorted({template_from_xbrl(r.get("xbrl")) for r in q[sym]["records"] + a[sym]["records"] if r.get("xbrl")}),
        })

    result = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "research_only": True,
        "live_authority": "none",
        "live_model_changed": False,
        "live_allocation_changed": False,
        "policy_id": POLICY["policy_id"],
        "scope": "development months only; no holdout official target fetches",
        "source_cutoff_rule": "Exchange dissemination timestamp <= 15:30 India-time-equivalent naive timestamp on the official constituent snapshot date; broadcast then filing date are fallbacks when dissemination time is unavailable.",
        "development_snapshots": signal_maps,
        "source_coverage_by_symbol": per_symbol,
        "summary": {
            "development_months": len(snapshots),
            "development_constituent_rows": sum(len(x["companies"]) for x in signal_maps),
            "unique_development_symbols": len(symbols),
            "company_months_with_complete_ttm_and_annual_sources": len(complete_keys),
            "company_months_total": sum(len(x["companies"]) for x in signal_maps),
            "source_gaps": len(gaps),
            "template_counts_in_selected_sources": template_counts,
            "symbols_with_zero_quarterly_records": [x["symbol"] for x in per_symbol if x["quarterly_records"] == 0],
            "symbols_with_zero_annual_records": [x["symbol"] for x in per_symbol if x["annual_records"] == 0],
            "symbols_with_any_unavailable_route": [
                x["symbol"] for x in per_symbol
                if any(a.get("status") != "ok" for a in x["quarterly_attempts"] + x["annual_attempts"] + x["corporate_action_attempts"])
            ],
            "holdout_target_fetch_count": 0,
        },
        "gaps": gaps,
        "interpretation_guardrail": "This maps official filing metadata only. It does not yet parse profit, net worth, share capital or dividends, does not reproduce a NIFTY valuation ratio, and cannot alter V3.13.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    return result


if __name__ == "__main__":
    build()
