#!/usr/bin/env python3
"""V1.2 first-party Nestle source resolution for the blinded development sample.

This revision changes source identity only. It does not parse accounting values,
inspect any valuation target, or alter V3.13. The five non-Nestle residual paths
remain exactly those in V1.1. NESTLEIND alone may use the explicitly frozen
issuer-hosted packets in development_residual_source_policy_v1.json.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

import pandas as pd

import development_residual_source_resolver_v11 as v11

v1 = v11.v1
POLICY = v1.POLICY
NESTLE_POLICY = POLICY["nestle_issuer_fallback"]
NESTLE_HOST = NESTLE_POLICY["allowed_host"]


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _download_issuer_pdf(session, url: str) -> bytes:
    p = urlparse(url)
    if p.scheme != "https" or p.hostname != NESTLE_HOST:
        raise ValueError("non-frozen Nestle issuer host refused")
    r = session.get(url, timeout=35, headers={**v1.base.UA, "Referer": "https://www.nestle.in/investors/stockandfinancials/financialresults"})
    r.raise_for_status()
    raw = r.content
    if len(raw) < 1000 or not raw.lstrip().startswith(b"%PDF"):
        raise ValueError("issuer attachment is not a plausible PDF")
    return raw


def _period_visible(text: str, period_end: str) -> bool:
    d = pd.Timestamp(period_end)
    variants = [
        rf"\b{d.day:02d}[./-]{d.month:02d}[./-]{d.year}\b",
        rf"\b{d.day}[./-]{d.month}[./-]{d.year}\b",
        rf"\b{d.day:02d}\s+{d.strftime('%B')}\s+{d.year}\b",
        rf"\b{d.day}\s+{d.strftime('%B')}\s+{d.year}\b",
        rf"\b{d.strftime('%B')}\s+{d.day},?\s+{d.year}\b",
    ]
    flat = re.sub(r"\s+", " ", text)
    return any(re.search(p, flat, flags=re.I) for p in variants)


def _looks_audited(text: str) -> bool:
    upper = text[:25000].upper().replace("UNAUDITED", "").replace("UN-AUDITED", "")
    return bool(re.search(r"\bAUDITED\b", upper))


def _looks_unaudited(text: str) -> bool:
    upper = text[:25000].upper()
    return "UNAUDITED" in upper or "UN-AUDITED" in upper


def nestle_issuer_sources(session) -> dict:
    sources = []
    attempts = []
    for spec in NESTLE_POLICY["sources"]:
        url = spec["url"]
        try:
            raw = _download_issuer_pdf(session, url)
            text = v1.base.pilot.pdf_to_text(raw)
            if not _period_visible(text, spec["period_end"]):
                raise ValueError(f"expected period end {spec['period_end']} not visible in issuer packet")
            if spec["audited_annual"] and not _looks_audited(text):
                raise ValueError("frozen annual source does not visibly contain audited result language")
            if spec["source_id"] == "nestle-q4-2023" and not _looks_unaudited(text):
                raise ValueError("Dec-2023 transition packet is not visibly marked unaudited")
            pub = pd.Timestamp(spec["publication_date"]) + pd.Timedelta(hours=23, minutes=59, seconds=59)
            sources.append({
                "symbol": "NESTLEIND",
                "queried_symbol": "NESTLEIND",
                "source_kind": "first_party_issuer_ir_pdf",
                "source_id": spec["source_id"],
                "public_timestamp": pub.isoformat(),
                "public_timestamp_precision": "date_only_conservative_end_of_day",
                "period_end": spec["period_end"],
                "consolidated_available": False,
                "audited_indicator": bool(spec["audited_annual"]),
                "attachment_url": url,
                "sha256": _sha256(raw),
                "description": "Frozen Nestle India first-party financial-result packet",
                "attachment_text": "issuer-hosted financial results",
            })
            attempts.append({
                "source_id": spec["source_id"],
                "url": url,
                "status": "ok",
                "period_end": spec["period_end"],
                "sha256": _sha256(raw),
            })
        except Exception as e:
            attempts.append({
                "source_id": spec["source_id"],
                "url": url,
                "status": "unavailable",
                "error": f"{type(e).__name__}: {e}",
            })
    return {"symbol": "NESTLEIND", "attempts": attempts, "sources": sources}


_BASE_ANNOUNCEMENT_SOURCES = v11.announcement_result_sources


def announcement_result_sources(session, symbol: str) -> dict:
    if symbol == "NESTLEIND":
        return nestle_issuer_sources(session)
    return _BASE_ANNOUNCEMENT_SOURCES(session, symbol)


# Bind only the source identity route consumed by the already-reviewed V1 build.
v1.announcement_result_sources = announcement_result_sources


if __name__ == "__main__":
    v1.build()
