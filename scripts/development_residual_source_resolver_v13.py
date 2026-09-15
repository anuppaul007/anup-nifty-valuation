#!/usr/bin/env python3
"""V1.3 official-exchange transport repair for Nestle development sources.

Research only; zero live authority. V1.3 does not alter the economic source
periods frozen in V1.2 and does not inspect any NIFTY valuation target. It only
replaces an issuer-CDN transport path that returned HTTP 403 in GitHub Actions
with exact, frozen BSE/NSE official-exchange PDF mirrors.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

import pandas as pd

import development_residual_source_resolver_v12 as v12

v1 = v12.v1
POLICY = v1.POLICY
EXCHANGE_POLICY = POLICY["nestle_exchange_mirror_fallback"]
ALLOWED_HOSTS = set(EXCHANGE_POLICY["allowed_hosts"])


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _allowed_exchange_path(host: str, path: str) -> bool:
    if host == "www.bseindia.com":
        return path.startswith("/xml-data/corpfiling/AttachHis/") and path.lower().endswith(".pdf")
    if host == "nsearchives.nseindia.com":
        return path.startswith("/corporate/") and path.lower().endswith(".pdf")
    return False


def _download_exchange_pdf(session, spec: dict) -> bytes:
    url = str(spec["url"])
    p = urlparse(url)
    expected_host = str(spec["host"])
    if p.scheme != "https" or p.hostname != expected_host or p.hostname not in ALLOWED_HOSTS:
        raise ValueError("non-frozen official exchange host refused")
    if not _allowed_exchange_path(p.hostname, p.path):
        raise ValueError("official exchange URL path outside frozen attachment namespace")
    referer = "https://www.bseindia.com/" if p.hostname == "www.bseindia.com" else v1.ANN_PAGE
    r = session.get(url, timeout=35, headers={**v1.base.UA, "Referer": referer})
    r.raise_for_status()
    raw = r.content
    if len(raw) < 1000 or not raw.lstrip().startswith(b"%PDF"):
        raise ValueError("exchange attachment is not a plausible PDF")
    return raw


def _nestle_identity_visible(text: str) -> bool:
    flat = re.sub(r"\s+", " ", text[:30000])
    company = bool(re.search(r"NESTL[ÉE]\s+INDIA", flat, flags=re.I))
    security = "500790" in flat.replace(" ", "") or "NESTLEIND" in flat.upper()
    return company and security


def _period_visible(text: str, period_end: str) -> bool:
    """Recognize one exact expected period despite harmless PDF layout variance.

    The test remains fail-closed: it searches only for the supplied frozen date.
    It accepts common exchange-PDF typography (spaces around numeric separators,
    ordinal suffixes, commas and abbreviated/full English month names) rather
    than inferring a reporting period from nearby dates.
    """
    d = pd.Timestamp(period_end)
    day = str(d.day)
    month_num = str(d.month)
    year = str(d.year)
    full = d.strftime("%B")
    abbr = d.strftime("%b")
    flat = re.sub(r"\s+", " ", text[:50000])
    ordinal = r"(?:st|nd|rd|th)?"
    month_word = rf"(?:{re.escape(full)}|{re.escape(abbr)}\.?)"
    patterns = [
        rf"(?<!\d){day}\s*[./-]\s*0?{month_num}\s*[./-]\s*{year}(?!\d)",
        rf"(?<!\d)0?{day}\s*[./-]\s*0?{month_num}\s*[./-]\s*{year}(?!\d)",
        rf"\b{day}{ordinal}\s+{month_word}\s*,?\s*{year}\b",
        rf"\b{month_word}\s+{day}{ordinal}\s*,?\s*{year}\b",
    ]
    return any(re.search(pattern, flat, flags=re.I) for pattern in patterns)


def nestle_exchange_sources(session) -> dict:
    sources: list[dict] = []
    attempts: list[dict] = []
    cache: dict[str, tuple[bytes, str]] = {}

    for spec in EXCHANGE_POLICY["sources"]:
        url = str(spec["url"])
        try:
            if url not in cache:
                raw = _download_exchange_pdf(session, spec)
                text = v1.base.pilot.pdf_to_text(raw)
                cache[url] = (raw, text)
            else:
                raw, text = cache[url]

            if not _nestle_identity_visible(text):
                raise ValueError("Nestle India / exchange security identity not visible")
            if not _period_visible(text, spec["period_end"]):
                raise ValueError(f"expected period end {spec['period_end']} not visible in exchange packet")
            if spec["audited_annual"] and not v12._looks_audited(text):
                raise ValueError("frozen audited annual-book comparative lacks visible audited language")
            if spec["source_id"] == "nestle-exchange-q4-2023" and not v12._looks_unaudited(text):
                raise ValueError("Dec-2023 transition result is not visibly marked unaudited")

            pub = pd.Timestamp(spec["publication_date"]) + pd.Timedelta(hours=23, minutes=59, seconds=59)
            host = urlparse(url).hostname
            source_kind = (
                "official_bse_historical_result_pdf"
                if host == "www.bseindia.com"
                else "official_nse_archive_result_pdf"
            )
            digest = _sha256(raw)
            sources.append({
                "symbol": "NESTLEIND",
                "queried_symbol": "NESTLEIND",
                "source_kind": source_kind,
                "source_id": spec["source_id"],
                "evidence_role": spec["evidence_role"],
                "public_timestamp": pub.isoformat(),
                "public_timestamp_precision": "date_only_conservative_end_of_day",
                "period_end": spec["period_end"],
                "consolidated_available": False,
                "audited_indicator": bool(spec["audited_annual"]),
                "attachment_url": url,
                "sha256": digest,
                "description": "Frozen Nestle India official-exchange financial-result packet",
                "attachment_text": "official exchange-hosted financial results",
            })
            attempts.append({
                "source_id": spec["source_id"],
                "url": url,
                "status": "ok",
                "period_end": spec["period_end"],
                "sha256": digest,
            })
        except Exception as exc:
            attempts.append({
                "source_id": spec["source_id"],
                "url": url,
                "status": "unavailable",
                "error": f"{type(exc).__name__}: {exc}",
            })

    return {
        "symbol": "NESTLEIND",
        "attempts": attempts,
        "sources": sources,
        "distinct_urls_requested": len(cache),
    }


_BASE_ANNOUNCEMENT_SOURCES = v12.announcement_result_sources


def announcement_result_sources(session, symbol: str) -> dict:
    if symbol == "NESTLEIND":
        return nestle_exchange_sources(session)
    return _BASE_ANNOUNCEMENT_SOURCES(session, symbol)


# The already-reviewed V1 build consumes this route. Bind only source transport.
v1.announcement_result_sources = announcement_result_sources


if __name__ == "__main__":
    v1.build()
