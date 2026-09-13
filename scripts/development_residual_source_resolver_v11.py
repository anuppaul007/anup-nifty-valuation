#!/usr/bin/env python3
"""V1.1 source-routing corrections for the development residual resolver.

This module changes source collection only, based on the diagnostic-only source
probe. It does not inspect any valuation target. The 30-month holdout remains
sealed and V3.13 retains zero dependency on this research code.
"""
from __future__ import annotations

import re

import pandas as pd

import development_residual_source_resolver as v1

base = v1.base


def financial_result_like(record: dict) -> bool:
    desc = str(record.get("desc") or "").strip().lower()
    text = str(record.get("attchmntText") or "").strip().lower()
    if "financial result" in desc:
        return True
    if "reply to clarification" in desc and "financial result" in desc:
        return True
    if "outcome of board meeting" in desc:
        return ("financial result" in text or "financial statement" in text) and any(
            token in text for token in ("period ended", "quarter ended", "year ended", "half year ended")
        )
    return False


def metadata_period_end(record: dict) -> pd.Timestamp | None:
    """Read an exact reporting period end from official NSE announcement text.

    The rule is intentionally narrow: the date must follow an 'ended' phrase.
    Month/year-only inference is permitted only for calendar quarter-end months.
    """
    text = " ".join(str(record.get(k) or "") for k in ("desc", "attchmntText"))
    month_words = "Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
    full_patterns = [
        rf"ended(?:\s+on)?\s+(\d{{1,2}}(?:st|nd|rd|th)?[\s./-]+(?:{month_words})[\s,./-]+\d{{2,4}})",
        rf"ended(?:\s+on)?\s+((?:{month_words})[\s./-]+\d{{1,2}}(?:st|nd|rd|th)?[,]?[\s./-]+\d{{2,4}})",
        r"ended(?:\s+on)?\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    ]
    for pattern in full_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            d = v1._parse_date_token(m.group(1))
            if d is not None and (d.month, d.day) in v1.QUARTER_ENDS:
                return d

    m = re.search(rf"ended(?:\s+on)?\s+({month_words})[\s,./-]+(\d{{4}})\b", text, flags=re.I)
    if not m:
        return None
    mon = v1.MONTHS.get(m.group(1).lower().rstrip("."))
    year = int(m.group(2))
    last_day = {3: 31, 6: 30, 9: 30, 12: 31}.get(mon)
    return pd.Timestamp(year=year, month=mon, day=last_day) if last_day else None


def announcement_result_sources(session, symbol: str) -> dict:
    fetched = v1.fetch_announcements(session, symbol)
    parsed = []
    diagnostics = {"metadata_period_end": 0, "pdf_period_end": 0, "download_or_parse_failures": 0}
    for record in fetched["records"]:
        if not financial_result_like(record):
            continue
        url = v1._official_attachment_url(record)
        ts = v1._announcement_timestamp(record)
        if not url or ts is None or not url.lower().split("?")[0].endswith(".pdf"):
            continue
        try:
            raw = v1._download_pdf(session, url)
            text = base.pilot.pdf_to_text(raw)
            pe = metadata_period_end(record)
            source = "official_nse_announcement_metadata"
            if pe is not None:
                diagnostics["metadata_period_end"] += 1
            else:
                pe = v1.current_period_end_from_pdf(text, ts)
                source = "official_nse_announcement_pdf"
                if pe is not None:
                    diagnostics["pdf_period_end"] += 1
            if pe is None:
                continue
            parsed.append({
                "symbol": symbol,
                "queried_symbol": symbol,
                "source_kind": source,
                "public_timestamp": ts.isoformat(),
                "period_end": str(pe.date()),
                "consolidated_available": v1._consolidated_indicator(text),
                "audited_indicator": v1._audited_indicator(text),
                "attachment_url": url,
                "description": record.get("desc"),
                "attachment_text": record.get("attchmntText"),
            })
        except Exception:
            diagnostics["download_or_parse_failures"] += 1
            continue
    by_period = {}
    for record in parsed:
        key = (record["period_end"], bool(record["consolidated_available"]))
        old = by_period.get(key)
        if old is None or pd.Timestamp(record["public_timestamp"]) > pd.Timestamp(old["public_timestamp"]):
            by_period[key] = record
    return {
        "symbol": symbol,
        "attempts": fetched["attempts"],
        "sources": list(by_period.values()),
        "diagnostics": diagnostics,
    }


def fetch_financial_complete(session, symbol: str, period: str) -> dict:
    """Union default and explicit historical routes even when default is non-empty."""
    url = "https://www.nseindia.com/api/corporates-financial-results"
    base_params = {"index": "equities", "symbol": symbol, "period": period}
    attempts = []
    records = []
    for params, label in (
        (base_params, "symbol_default"),
        ({**base_params, "from_date": base.DATE_START, "to_date": base.DATE_END}, "symbol_explicit_date_window"),
    ):
        got, attempt = base._attempt(session, url, params, label, base.FINANCIAL_PAGE)
        attempts.append(attempt)
        records.extend(got)
    return {"symbol": symbol, "period": period, "records": base._dedupe(records), "attempts": attempts}


def structured_sources(session, original_symbol: str) -> dict:
    symbols = [original_symbol]
    if original_symbol in v1.ALIASES:
        symbols.append(v1.ALIASES[original_symbol])
    quarterly = []
    annual = []
    attempts = []
    for symbol in symbols:
        qr = fetch_financial_complete(session, symbol, "Quarterly")
        ar = fetch_financial_complete(session, symbol, "Annual")
        quarterly.extend(v1._annotate_query(qr["records"], symbol))
        annual.extend(v1._annotate_query(ar["records"], symbol))
        attempts.append({
            "queried_symbol": symbol,
            "quarterly": qr["attempts"],
            "annual": ar["attempts"],
            "quarterly_records": len(qr["records"]),
            "annual_records": len(ar["records"]),
        })
    return {"quarterly": base._dedupe(quarterly), "annual": base._dedupe(annual), "attempts": attempts}


# Bind only the source-routing functions used by the already-reviewed build.
v1._financial_result_like = financial_result_like
v1.announcement_result_sources = announcement_result_sources
v1.structured_sources = structured_sources


if __name__ == "__main__":
    v1.build()
