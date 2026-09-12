#!/usr/bin/env python3
"""Current-definition NIFTY 50 reconstruction feasibility and coverage audit.

Research only. This module does NOT modify model.js, multiasset.py, latest.json,
or any prospective archived decision.

Goal
----
Reconstruct historical NIFTY 50 valuation ratios using:
  * the actual historical NIFTY constituent weights in force at each date; and
  * today's accounting definitions for index P/E, P/B and dividend yield;
  * only company information that had been filed/announced by the signal date.

This is intentionally different from a counterfactual "free-float NIFTY since
2000". NIFTY changed to free-float weighting only in June 2009. The research
question here is the effect of today's *accounting definitions*, so historical
index weights are preserved as actually published.

The module has two roles:
1) exact deterministic aggregation/point-in-time eligibility primitives that
   future reconstruction rows must satisfy; and
2) a public-source coverage audit that refuses to manufacture missing history.

A month is not labelled reconstructable until all required constituent fields
pass point-in-time and weight-completeness checks.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
import json
import math
import re
import zipfile

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "current_definition_reconstruction.json"

UA = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AnupNiftyValuation/3.6; "
        "personal non-commercial research)"
    )
}

# Official definition / source inventory. These are recorded as evidence, not
# treated as proof that every historical observation is already machine-readable.
OFFICIAL_SOURCES = {
    "current_pe_definition": {
        "url": "https://www.niftyindices.com/resources/index-concepts/price-earnings-ratio",
        "rule": (
            "Index market capitalisation divided by index earnings; constituent "
            "earnings use trailing four quarters consolidated financials where "
            "available, with standalone fallback where consolidated results are unavailable."
        ),
    },
    "current_pb_definition": {
        "url": "https://www.niftyindices.com/resources/index-concepts/price-to-book-value",
        "rule": (
            "Index market capitalisation divided by index book value; consolidated "
            "net worth is used where available, with standalone fallback."
        ),
    },
    "current_dy_definition": {
        "url": "https://www.niftyindices.com/resources/index-concepts/dividend-yield",
        "rule": "Rolling twelve-month equity dividends based on ex-dividend date divided by market capitalisation.",
    },
    "weight_archive_monthly": {
        "url": "https://www.niftyindices.com/reports/monthly-reports",
        "rule": "Official monthly reports include Indices Market Capitalisation & Weightage archives.",
    },
    "ismr_2001": {
        "url": "https://nsearchives.nseindia.com/web/sites/default/files/inline-files/ismr.pdf",
        "rule": (
            "NSE Indian Securities Market Review 2001, Annexure 4.2, publishes "
            "monthly S&P CNX Nifty security weights from Apr-2000 through Jun-2001."
        ),
    },
    "financial_results": {
        "url": "https://www.nseindia.com/companies-listing/corporate-filings-financial-results",
        "api": "https://www.nseindia.com/api/corporates-financial-results",
        "rule": "NSE corporate financial-result filings; XBRL links are used where supplied.",
    },
    "corporate_actions": {
        "url": "https://www.nseindia.com/companies-listing/corporate-filings-actions",
        "api": "https://www.nseindia.com/api/corporates-corporateActions",
        "rule": "NSE corporate actions, including dividend ex-dates and share splits/bonuses.",
    },
}

# Verified chronology from official NSE/Nifty methodology publications.
METHODOLOGY = {
    "weighting": {
        "pre_2009_06_26": "actual historical NIFTY weighting then in force",
        "from_2009_06_26": "free-float market-capitalisation weighting",
        "source": "https://www.nseindia.com/products-services/indices-nifty50-index",
    },
    "accounting_target": {
        "pe": "trailing-four-quarter consolidated earnings, standalone fallback",
        "pb": "consolidated net worth from latest eligible annual financials, standalone fallback",
        "dy": "rolling-12-month equity dividends by ex-dividend date",
    },
}

# The later monthly-archive filename pattern is public on the Nifty Indices
# archive UI. We probe representative months only; lack of access in CI is a
# network result, not evidence that the archive itself does not exist.
WEIGHT_ARCHIVE_PROBES = [
    ("2013-09", "https://www.niftyindices.com/Indices_-_Market_Capitalisation_and_Weightage/indices_dataSep2013.zip"),
    ("2015-01", "https://www.niftyindices.com/Indices_-_Market_Capitalisation_and_Weightage/indices_dataJan2015.zip"),
    ("2020-01", "https://www.niftyindices.com/Indices_-_Market_Capitalisation_and_Weightage/indices_dataJan2020.zip"),
    ("2023-09", "https://www.niftyindices.com/Indices_-_Market_Capitalisation_and_Weightage/indices_dataSep2023.zip"),
]

# Representative companies chosen to exercise banking, IT, energy, consumer,
# industrial and financial statement templates. This is a source-coverage probe,
# not a claim of full index reconstruction.
FINANCIAL_PROBE_SYMBOLS = [
    "RELIANCE",
    "HDFCBANK",
    "ICICIBANK",
    "TCS",
    "INFY",
    "ITC",
    "LT",
    "SBIN",
]


def finite(x):
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def normalize_weights(weights, tolerance=0.015):
    """Return normalised decimal weights, rejecting incomplete snapshots.

    Published monthly tables may sum to 99.99/100.01 because of display
    rounding. Materially incomplete snapshots are rejected rather than silently
    renormalised.
    """
    s = pd.Series(weights, dtype="float64")
    if s.empty or s.isna().any() or (s < 0).any():
        raise ValueError("weights must be complete, finite and non-negative")
    total = float(s.sum())
    if not math.isfinite(total) or total <= 0:
        raise ValueError("invalid weight total")
    # Accept either decimal or percentage input.
    if total > 2.0:
        s = s / 100.0
        total = float(s.sum())
    if abs(total - 1.0) > float(tolerance):
        raise ValueError(f"incomplete index weights: sum={total:.6f}")
    return s / total


def aggregate_current_definition(weights, pe, pb, dividend_yield_pct):
    """Aggregate constituent ratios using exact index weights.

    Algebra:
      PE_index = 1 / sum(w_i / PE_i)
      PB_index = 1 / sum(w_i / PB_i)
      DY_index = sum(w_i * DY_i)

    Therefore exact historical IWFs are not separately required once the actual
    historical index weights are known. IWF/capping effects are already embedded
    in those published weights.
    """
    w = normalize_weights(weights)
    pe = pd.Series(pe, dtype="float64")
    pb = pd.Series(pb, dtype="float64")
    dy = pd.Series(dividend_yield_pct, dtype="float64")
    if not (len(w) == len(pe) == len(pb) == len(dy)):
        raise ValueError("constituent arrays must have identical length")
    if pe.isna().any() or pb.isna().any() or dy.isna().any():
        raise ValueError("missing constituent valuation field")
    if (pe <= 0).any() or (pb <= 0).any() or (dy < 0).any():
        raise ValueError("invalid constituent valuation field")
    pe_den = float((w / pe).sum())
    pb_den = float((w / pb).sum())
    if pe_den <= 0 or pb_den <= 0:
        raise ValueError("invalid aggregate denominator")
    return {
        "pe": 1.0 / pe_den,
        "pb": 1.0 / pb_den,
        "dividend_yield_pct": float((w * dy).sum()),
    }


def point_in_time_eligible(filing_or_announcement_time, signal_time):
    """True only when the information was public no later than the signal."""
    a = pd.Timestamp(filing_or_announcement_time)
    s = pd.Timestamp(signal_time)
    if a.tzinfo is not None:
        a = a.tz_convert(None)
    if s.tzinfo is not None:
        s = s.tz_convert(None)
    return bool(a <= s)


def current_definition_company_inputs(
    *, market_cap, ttm_earnings, book_value, rolling_12m_dividends
):
    """Convert point-in-time accounting numerators to company valuation ratios."""
    vals = [market_cap, ttm_earnings, book_value, rolling_12m_dividends]
    if not all(finite(x) for x in vals):
        raise ValueError("all company inputs must be finite")
    mc, earn, book, divs = map(float, vals)
    if mc <= 0 or earn <= 0 or book <= 0 or divs < 0:
        raise ValueError("non-positive denominator or negative dividends")
    return {
        "pe": mc / earn,
        "pb": mc / book,
        "dividend_yield_pct": 100.0 * divs / mc,
    }


def month_reconstructable(rows, expected_members=50, min_weight_sum=0.985):
    """Strict gate for calling a historical month reconstructable.

    `rows` contains one row per constituent with keys:
      weight, pe, pb, dividend_yield_pct, filing_ok, dividend_history_ok.
    No neutral fill, imputation or cross-sectional scaling is allowed.
    """
    if len(rows) != int(expected_members):
        return False, f"member_count={len(rows)}"
    required = ("weight", "pe", "pb", "dividend_yield_pct")
    for r in rows:
        if not all(finite(r.get(k)) for k in required):
            return False, "missing_valuation_field"
        if not r.get("filing_ok", False):
            return False, "filing_not_point_in_time"
        if not r.get("dividend_history_ok", False):
            return False, "dividend_history_incomplete"
    total = sum(float(r["weight"]) for r in rows)
    if total > 2:
        total /= 100.0
    if total < float(min_weight_sum):
        return False, f"weight_sum={total:.6f}"
    return True, "complete"


def _session():
    s = requests.Session()
    s.headers.update(UA)
    # Best-effort cookie/bootstrap. Failure is reported by individual probes.
    for url in ("https://www.nseindia.com/", "https://www.niftyindices.com/"):
        try:
            s.get(url, timeout=12)
        except Exception:
            pass
    return s


def _get_json(session, url, params=None, timeout=18):
    r = session.get(url, params=params, timeout=timeout, headers={**UA, "Accept": "application/json,text/plain,*/*"})
    r.raise_for_status()
    return r.json()


def _parse_dates_from_record(record):
    out = []
    for k, v in (record or {}).items():
        if not isinstance(v, str):
            continue
        if "date" not in str(k).lower() and "time" not in str(k).lower():
            continue
        d = pd.to_datetime(v, errors="coerce", dayfirst=True)
        if not pd.isna(d):
            out.append((str(k), d))
    return out


def probe_financial_results(session, symbol):
    url = OFFICIAL_SOURCES["financial_results"]["api"]
    try:
        data = _get_json(session, url, {"index": "equities", "symbol": symbol, "period": "Quarterly"})
        records = data if isinstance(data, list) else (data.get("data") if isinstance(data, dict) else None)
        records = records if isinstance(records, list) else []
        dates = []
        consolidated_mentions = 0
        xbrl_links = 0
        for r in records:
            dates.extend(d for _, d in _parse_dates_from_record(r))
            text = " ".join(str(v) for v in r.values()).lower()
            consolidated_mentions += int("consolidated" in text)
            xbrl_links += sum("xbrl" in str(v).lower() for v in r.values())
        return {
            "symbol": symbol,
            "status": "ok",
            "records": len(records),
            "earliest_dated_record": str(min(dates).date()) if dates else None,
            "latest_dated_record": str(max(dates).date()) if dates else None,
            "records_mentioning_consolidated": consolidated_mentions,
            "xbrl_link_mentions": int(xbrl_links),
        }
    except Exception as e:
        return {"symbol": symbol, "status": "unavailable", "error": f"{type(e).__name__}: {e}"}


def probe_corporate_actions(session, symbol):
    url = OFFICIAL_SOURCES["corporate_actions"]["api"]
    try:
        data = _get_json(session, url, {"index": "equities", "symbol": symbol})
        records = data if isinstance(data, list) else (data.get("data") if isinstance(data, dict) else None)
        records = records if isinstance(records, list) else []
        dividend_rows = []
        dates = []
        for r in records:
            text = " ".join(str(v) for v in r.values()).lower()
            if "dividend" not in text:
                continue
            dividend_rows.append(r)
            for _, d in _parse_dates_from_record(r):
                dates.append(d)
        return {
            "symbol": symbol,
            "status": "ok",
            "records": len(records),
            "dividend_records": len(dividend_rows),
            "earliest_dividend_date_seen": str(min(dates).date()) if dates else None,
            "latest_dividend_date_seen": str(max(dates).date()) if dates else None,
        }
    except Exception as e:
        return {"symbol": symbol, "status": "unavailable", "error": f"{type(e).__name__}: {e}"}


def probe_weight_zip(session, month, url):
    try:
        r = session.get(url, timeout=20, headers={**UA, "Referer": "https://www.niftyindices.com/reports/monthly-reports"})
        r.raise_for_status()
        raw = r.content
        if not zipfile.is_zipfile(BytesIO(raw)):
            return {"month": month, "status": "not_zip", "http_status": r.status_code, "bytes": len(raw)}
        with zipfile.ZipFile(BytesIO(raw)) as z:
            names = z.namelist()
        return {
            "month": month,
            "status": "ok",
            "http_status": r.status_code,
            "bytes": len(raw),
            "files": names[:30],
            "file_count": len(names),
        }
    except Exception as e:
        return {"month": month, "status": "unavailable", "error": f"{type(e).__name__}: {e}"}


def fetch_current_constituent_count(session):
    url = "https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv"
    try:
        r = session.get(url, timeout=18, headers={**UA, "Referer": "https://www.niftyindices.com/indices/equity/broad-based-indices/NIFTY-50"})
        r.raise_for_status()
        q = pd.read_csv(StringIO(r.text.lstrip("\ufeff")))
        cols = {re.sub(r"[^a-z0-9]", "", str(c).lower()): c for c in q.columns}
        sc = next((cols[k] for k in ("symbol", "ticker") if k in cols), None)
        symbols = q[sc].dropna().astype(str).tolist() if sc else []
        return {"status": "ok", "rows": int(len(q)), "symbols_found": len(symbols), "sample": symbols[:10]}
    except Exception as e:
        return {"status": "unavailable", "error": f"{type(e).__name__}: {e}"}


def build():
    s = _session()
    financial = [probe_financial_results(s, x) for x in FINANCIAL_PROBE_SYMBOLS]
    actions = [probe_corporate_actions(s, x) for x in FINANCIAL_PROBE_SYMBOLS]
    weights = [probe_weight_zip(s, m, u) for m, u in WEIGHT_ARCHIVE_PROBES]
    current = fetch_current_constituent_count(s)

    fin_ok = [x for x in financial if x.get("status") == "ok"]
    act_ok = [x for x in actions if x.get("status") == "ok"]
    weight_ok = [x for x in weights if x.get("status") == "ok"]

    # Evidence classification deliberately separates "source exists" from
    # "machine probe worked in this CI run" and from "fully reconstructed".
    result = {
        "status": "complete",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "research_only": True,
        "live_model_changed": False,
        "live_allocation_changed": False,
        "target_definition": {
            "question": "Historical NIFTY 50 using actual historical index weights but today's accounting definitions, point-in-time only.",
            "counterfactual_free_float_since_2000": False,
            "accounting": METHODOLOGY["accounting_target"],
        },
        "official_sources": OFFICIAL_SOURCES,
        "historical_weight_evidence": {
            "verified_start": "2000-04",
            "verified_official_example": "NSE ISMR 2001 Annexure 4.2 publishes monthly constituent weights Apr-2000 through Jun-2001, with inclusion markers.",
            "later_archive": "Nifty Indices monthly reports expose market-capitalisation/weightage ZIP archives; representative URLs are probed below.",
            "key_implication": "Actual published index weights embed the weighting/IWF regime, so IWF need not be separately reconstructed for ratio aggregation.",
        },
        "machine_probes": {
            "current_constituents": current,
            "weight_archives": weights,
            "financial_results": financial,
            "corporate_actions": actions,
        },
        "probe_summary": {
            "financial_symbols_ok": len(fin_ok),
            "financial_symbols_total": len(financial),
            "corporate_action_symbols_ok": len(act_ok),
            "corporate_action_symbols_total": len(actions),
            "weight_archive_months_ok": len(weight_ok),
            "weight_archive_months_total": len(weights),
        },
        "reconstruction_gate": {
            "required_for_each_month": [
                "exact official constituent set and actual index weights",
                "TTM consolidated earnings known by signal date, standalone fallback only where consolidated unavailable",
                "latest eligible consolidated net worth known by signal date, standalone fallback only where consolidated unavailable",
                "rolling-12-month cash dividends using ex-dates known by signal date",
                "company market capitalisation / price-share basis consistent with the financial numerators",
                "corporate-action adjustment continuity",
                "all 50 constituent rows passing the point-in-time gate",
            ],
            "missing_value_policy": "fail closed; no neutral fill, interpolation, cross-sectional imputation or one-day methodology scaling",
            "earliest_fully_reconstructed_month": None,
            "reason": "This phase establishes source coverage and exact aggregation rules. No historical month is promoted until all 50 constituent accounting rows are independently assembled and validated.",
        },
        "next_validation_gate": {
            "pilot_period": "2023-09 onward",
            "test": "Reconstruct index PE/PB/DY from constituent rows and actual weights, then compare against published NIFTY ratios under the same current definitions.",
            "promotion_condition": "Only extend backward after the recent pilot reproduces published ratios within a pre-declared tolerance and all rows are point-in-time clean.",
        },
        "interpretation": (
            "Official weight history is no longer the principal conceptual blocker: NSE publications demonstrate monthly constituent weights from Apr-2000. "
            "The harder remaining task is complete point-in-time company accounting history under today's definitions, especially before modern XBRL filing coverage."
        ),
    }
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "weight_history_verified_start": result["historical_weight_evidence"]["verified_start"],
        **result["probe_summary"],
        "earliest_fully_reconstructed_month": None,
        "live_model_changed": False,
    }, separators=(",", ":")))
    return result


if __name__ == "__main__":
    build()
