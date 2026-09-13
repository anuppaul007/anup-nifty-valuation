#!/usr/bin/env python3
"""Diagnostic-only probe for unresolved official NSE announcement metadata.

No valuation target is fetched and no source becomes eligible because of this
probe. It records why historical HDFCLIFE, SBILIFE and NESTLEIND announcements
do or do not pass the frozen residual resolver's metadata gates.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from urllib.parse import urlparse

import development_residual_source_resolver as resolver

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "development_residual_announcement_probe.json"
SYMBOLS = ["HDFCLIFE", "SBILIFE", "NESTLEIND"]


def compact(r: dict) -> dict:
    u_raw = str(r.get("attchmntFile") or "").strip()
    p = urlparse(u_raw) if u_raw else None
    ts = resolver._announcement_timestamp(r)
    official = resolver._official_attachment_url(r)
    financial = resolver._financial_result_like(r)
    reasons = []
    if not financial:
        reasons.append("metadata_not_financial_result_like")
    if ts is None:
        reasons.append("missing_public_timestamp")
    if not official:
        reasons.append("attachment_not_absolute_https_nsearchives")
    if official and not official.lower().split("?")[0].endswith(".pdf"):
        reasons.append("attachment_not_pdf_suffix")
    return {
        "symbol": r.get("symbol"),
        "company": r.get("sm_name") or r.get("companyName"),
        "public_timestamp": ts.isoformat() if ts is not None else None,
        "desc": r.get("desc"),
        "attachment_text": r.get("attchmntText"),
        "attachment_file": u_raw or None,
        "attachment_scheme": p.scheme if p else None,
        "attachment_host": p.hostname if p else None,
        "financial_result_like": financial,
        "official_attachment_url": official,
        "metadata_rejection_reasons": reasons,
    }


def build() -> dict:
    session = resolver._session()
    per_symbol = {}
    for symbol in SYMBOLS:
        fetched = resolver.fetch_announcements(session, symbol)
        rows = [compact(r) for r in fetched["records"]]
        # Keep all financial-like rows plus board-outcome/result-adjacent rows so
        # the diagnostic can reveal an overly narrow metadata predicate.
        interesting = []
        for x in rows:
            text = f"{x.get('desc') or ''} {x.get('attachment_text') or ''}".lower()
            if x["financial_result_like"] or any(k in text for k in ("board meeting", "outcome", "quarter", "annual", "result")):
                interesting.append(x)
        per_symbol[symbol] = {
            "announcement_records": len(rows),
            "interesting_records": len(interesting),
            "financial_result_like_records": sum(x["financial_result_like"] for x in rows),
            "absolute_nsearchives_attachments": sum(bool(x["official_attachment_url"]) for x in rows),
            "interesting": interesting,
            "attempts": fetched["attempts"],
        }
    out = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "research_only": True,
        "live_authority": "none",
        "holdout_target_fetch_count": 0,
        "symbols": per_symbol,
        "guardrail": "Diagnostic metadata only. No record is made eligible by this probe and no holdout valuation target is fetched.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({s: {k:v for k,v in per_symbol[s].items() if k != 'interesting' and k != 'attempts'} for s in SYMBOLS}, indent=2))
    return out


if __name__ == "__main__":
    build()
