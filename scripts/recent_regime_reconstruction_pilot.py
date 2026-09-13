#!/usr/bin/env python3
"""Harvest official sources for a blinded recent-regime NIFTY reconstruction.

Research only. This stage does not reconstruct company fundamentals yet and has
no live allocation authority. It establishes whether official month-end weight
snapshots and development targets are machine-accessible while deliberately not
fetching holdout P/E/P/B/dividend-yield targets.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
import csv
import hashlib
import json
import re
import subprocess
import zipfile

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "recent_reconstruction_policy_v1.json"
OUT = ROOT / "data" / "recent_regime_source_ledger.json"
DEBUG = ROOT / "data" / "recent_regime_source_debug.txt"

UA = {
    "User-Agent": "Mozilla/5.0 (compatible; AnupNiftyValuation/recent-reconstruction-v1; personal non-commercial research)",
    "Accept": "text/html,application/xhtml+xml,application/pdf,application/zip,application/json,text/plain,*/*",
}

MONTH_ABBR = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def month_range(start: str, end: str) -> list[str]:
    s = pd.Period(start, freq="M")
    e = pd.Period(end, freq="M")
    if e < s:
        raise ValueError("end month precedes start month")
    return [str(x) for x in pd.period_range(s, e, freq="M")]


def month_tokens(month: str) -> tuple[str, str]:
    p = pd.Period(month, freq="M")
    mixed = f"{MONTH_ABBR[p.month]}{p.year}"
    return mixed, mixed.upper()


def dashboard_url(month: str) -> str:
    _, upper = month_tokens(month)
    return f"https://www.niftyindices.com/Index_Dashboard/Index_Dashboard_{upper}.pdf"


def weights_zip_url(month: str) -> str:
    mixed, _ = month_tokens(month)
    return f"https://www.niftyindices.com/Indices_-_Market_Capitalisation_and_Weightage/indices_data{mixed}.zip"


def target_fetch_allowed(month: str, policy: dict) -> bool:
    return month in set(policy["sample"]["development_months"])


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(UA)
    for url in ("https://www.niftyindices.com/", "https://www.nseindia.com/"):
        try:
            s.get(url, timeout=12)
        except Exception:
            pass
    return s


def _get_bytes(session: requests.Session, url: str, timeout: int = 25) -> bytes:
    r = session.get(url, timeout=timeout, headers={**UA, "Referer": "https://www.niftyindices.com/"})
    r.raise_for_status()
    return r.content


def pdf_to_text(raw: bytes) -> str:
    p = subprocess.run(
        ["pdftotext", "-layout", "-", "-"],
        input=raw,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {p.stderr.decode('utf-8', errors='replace')[:400]}")
    return p.stdout.decode("utf-8", errors="replace")


def parse_nifty50_dashboard(text: str) -> dict:
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not re.match(r"^Nifty\s*50\b", line, flags=re.I):
            continue
        nums = re.findall(r"(?<![A-Za-z])-?\d+(?:\.\d+)?", line)
        if len(nums) < 3:
            continue
        pe, pb, dy = map(float, nums[-3:])
        if pe <= 0 or pb <= 0 or dy < 0:
            raise ValueError(f"implausible Nifty 50 dashboard row: {line}")
        return {"pe": pe, "pb": pb, "dividend_yield_pct": dy, "source_row": line}
    raise ValueError("Nifty 50 valuation row not found in dashboard text")


def _weight_pdf_member(names: list[str], month: str) -> str:
    mixed, _ = month_tokens(month)
    want = re.sub(r"[^a-z0-9]", "", f"nifty50{mixed}.pdf".lower())
    scored = []
    for name in names:
        key = re.sub(r"[^a-z0-9]", "", name.lower())
        if "nifty50" in key and key.endswith("pdf"):
            scored.append((0 if want in key else 1, len(name), name))
    if not scored:
        raise FileNotFoundError("NIFTY 50 PDF not found inside monthly weight ZIP")
    return sorted(scored)[0][2]


def _numbers(line: str) -> list[float]:
    return [float(x.replace(",", "")) for x in re.findall(r"(?<![A-Za-z0-9])\d[\d,]*(?:\.\d+)?", line)]


def _preceding_weight(lines: list[str], idx: int) -> float | None:
    """Recover a wrapped row's weight from its preceding security-name line.

    In the official PDF a long security name can occupy the line immediately
    above the symbol row while the weight remains on that name line. Such a line
    has exactly one numeric field. A preceding completed constituent row has
    close, market-cap and weight (three numeric fields), so it is rejected.
    """
    for j in range(idx - 1, max(-1, idx - 4), -1):
        raw = lines[j].strip()
        if not raw:
            continue
        nums = _numbers(raw)
        if len(nums) == 1 and 0 < nums[0] < 30:
            return nums[0]
        return None
    return None


def parse_weight_table(text: str) -> tuple[list[dict], dict]:
    """Parse official NIFTY 50 symbol/close/index-MCap/weight rows."""
    lines = text.splitlines()
    rows: list[dict] = []
    seen = set()
    header_found = any("symbol" in x.lower() and "weight" in x.lower() for x in lines[:40])
    for i, raw in enumerate(lines):
        m = re.match(r"^\s*([A-Z0-9&-]{2,20})\s+", raw)
        if not m:
            continue
        symbol = m.group(1)
        if symbol in {"SYMBOL", "NIFTY", "INDEX", "NSE"} or symbol in seen:
            continue
        nums = _numbers(raw[m.end():])
        if len(nums) < 2:
            continue
        if len(nums) >= 3 and 0 < nums[-1] < 30:
            close_price, index_mcap, weight = nums[-3], nums[-2], nums[-1]
            weight_source = "symbol_line"
        else:
            close_price, index_mcap = nums[-2], nums[-1]
            weight = _preceding_weight(lines, i)
            weight_source = "preceding_wrapped_line"
        if weight is None:
            continue
        if close_price <= 0 or index_mcap <= 0 or not (0 < weight < 30):
            continue
        rows.append({
            "symbol": symbol,
            "close_price": close_price,
            "index_mcap_crore": index_mcap,
            "weight_pct": weight,
            "weight_source": weight_source,
            "raw_symbol_line": re.sub(r"\s+", " ", raw).strip(),
        })
        seen.add(symbol)
        if len(rows) == 50:
            break
    total = sum(x["weight_pct"] for x in rows)
    ok = len(rows) == 50 and 98.5 <= total <= 101.5 and len({x["symbol"] for x in rows}) == 50
    diagnostics = {
        "header_found": header_found,
        "candidate_rows": len(rows),
        "unique_symbols": len({x["symbol"] for x in rows}),
        "weight_sum_pct": total,
        "strict_ok": ok,
        "wrapped_weight_rows": sum(x["weight_source"] == "preceding_wrapped_line" for x in rows),
    }
    return (rows if ok else []), diagnostics


def parse_security_master_symbols(raw: bytes) -> set[str]:
    text = raw.decode("utf-8", errors="replace").lstrip("\ufeff")
    reader = csv.DictReader(StringIO(text))
    out = set()
    for row in reader:
        symbol = (row.get("SYMBOL") or row.get("Symbol") or "").strip()
        if symbol:
            out.add(symbol)
    return out


def _records_from_json(data) -> list[dict]:
    records = data if isinstance(data, list) else (data.get("data") if isinstance(data, dict) else [])
    return records if isinstance(records, list) else []


def probe_financial_api(session: requests.Session, symbol: str, include_schema: bool = False) -> dict:
    url = "https://www.nseindia.com/api/corporates-financial-results"
    try:
        r = session.get(url, params={"index": "equities", "symbol": symbol, "period": "Quarterly"}, timeout=20,
                        headers={**UA, "Accept": "application/json,text/plain,*/*", "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-financial-results"})
        r.raise_for_status()
        records = _records_from_json(r.json())
        filing_dates = []
        consolidated_rows = 0
        standalone_rows = 0
        xbrl_rows = 0
        for rec in records:
            if not isinstance(rec, dict):
                continue
            d = pd.to_datetime(rec.get("filingDate"), errors="coerce", dayfirst=True)
            if not pd.isna(d):
                filing_dates.append(d)
            c = str(rec.get("consolidated", "")).lower()
            consolidated_rows += int("consolidated" in c)
            standalone_rows += int("standalone" in c)
            xbrl_rows += int(bool(rec.get("xbrl")))
        out = {
            "symbol": symbol,
            "status": "ok",
            "records": len(records),
            "has_records": bool(records),
            "earliest_filing_date": str(min(filing_dates).date()) if filing_dates else None,
            "latest_filing_date": str(max(filing_dates).date()) if filing_dates else None,
            "consolidated_rows": consolidated_rows,
            "standalone_rows": standalone_rows,
            "xbrl_rows": xbrl_rows,
        }
        if include_schema:
            sample = records[0] if records else {}
            keys = sorted(str(k) for k in sample.keys()) if isinstance(sample, dict) else []
            out["keys"] = keys
            out["link_keys"] = sorted(k for k in keys if any(t in k.lower() for t in ("xbrl", "link", "url", "file")))
            out["date_keys"] = sorted(k for k in keys if any(t in k.lower() for t in ("date", "time")))
        return out
    except Exception as e:
        return {"symbol": symbol, "status": "unavailable", "has_records": False, "error": f"{type(e).__name__}: {e}"}


def probe_corporate_actions_api(session: requests.Session, symbol: str) -> dict:
    url = "https://www.nseindia.com/api/corporates-corporateActions"
    try:
        r = session.get(url, params={"index": "equities", "symbol": symbol}, timeout=20,
                        headers={**UA, "Accept": "application/json,text/plain,*/*", "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-actions"})
        r.raise_for_status()
        records = _records_from_json(r.json())
        dividend_rows = 0
        dated = []
        for rec in records:
            if not isinstance(rec, dict):
                continue
            text = " ".join(str(v) for v in rec.values()).lower()
            dividend_rows += int("dividend" in text)
            for key, value in rec.items():
                if not isinstance(value, str) or not any(t in str(key).lower() for t in ("date", "time")):
                    continue
                d = pd.to_datetime(value, errors="coerce", dayfirst=True)
                if not pd.isna(d):
                    dated.append(d)
        return {
            "symbol": symbol,
            "status": "ok",
            "records": len(records),
            "has_records": bool(records),
            "dividend_rows": dividend_rows,
            "earliest_dated_record": str(min(dated).date()) if dated else None,
            "latest_dated_record": str(max(dated).date()) if dated else None,
        }
    except Exception as e:
        return {"symbol": symbol, "status": "unavailable", "has_records": False, "error": f"{type(e).__name__}: {e}"}


def build() -> dict:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    months = month_range(policy["sample"]["start_month"], policy["sample"]["end_month"])
    if len(months) != policy["sample"]["completed_months"]:
        raise RuntimeError("policy month count mismatch")

    session = _session()
    security_master_url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    security_master_symbols: set[str] = set()
    security_master_status = {"status": "unavailable", "url": security_master_url}
    try:
        raw_master = _get_bytes(session, security_master_url)
        security_master_symbols = parse_security_master_symbols(raw_master)
        security_master_status = {
            "status": "ok", "symbols": len(security_master_symbols),
            "sha256": sha256_bytes(raw_master), "url": security_master_url,
        }
    except Exception as e:
        security_master_status["error"] = f"{type(e).__name__}: {e}"

    month_rows = []
    debug_chunks = []
    dev_targets_ok = weights_ok = parsed_symbol_rows = current_master_symbol_matches = 0

    for month in months:
        row = {
            "month": month,
            "tranche": "development" if target_fetch_allowed(month, policy) else "holdout",
            "weights": {"url": weights_zip_url(month), "status": "unavailable"},
            "official_target": {"status": "sealed_not_fetched" if not target_fetch_allowed(month, policy) else "unavailable"},
        }
        try:
            zip_raw = _get_bytes(session, weights_zip_url(month))
            if not zipfile.is_zipfile(BytesIO(zip_raw)):
                raise ValueError("monthly weight archive is not a ZIP")
            with zipfile.ZipFile(BytesIO(zip_raw)) as z:
                member = _weight_pdf_member(z.namelist(), month)
                pdf_raw = z.read(member)
            text = pdf_to_text(pdf_raw)
            parsed, diagnostics = parse_weight_table(text)
            current_matches = sum(1 for x in parsed if x["symbol"] in security_master_symbols)
            row["weights"] = {
                "url": weights_zip_url(month), "status": "ok" if parsed else "unparsed",
                "zip_sha256": sha256_bytes(zip_raw), "pdf_member": member,
                "pdf_sha256": sha256_bytes(pdf_raw), "diagnostics": diagnostics,
                "constituents": parsed, "current_security_master_symbol_matches": current_matches,
            }
            if parsed:
                weights_ok += 1
                parsed_symbol_rows += len(parsed)
                current_master_symbol_matches += current_matches
            if month == policy["sample"]["development_months"][0]:
                debug_chunks.append(f"===== {month} WEIGHT PDF TEXT =====\n{text[:16000]}")
        except Exception as e:
            row["weights"]["error"] = f"{type(e).__name__}: {e}"

        if target_fetch_allowed(month, policy):
            try:
                raw = _get_bytes(session, dashboard_url(month))
                text = pdf_to_text(raw)
                target = parse_nifty50_dashboard(text)
                row["official_target"] = {"status": "ok", "url": dashboard_url(month), "pdf_sha256": sha256_bytes(raw), **target}
                dev_targets_ok += 1
            except Exception as e:
                row["official_target"] = {"status": "unavailable", "url": dashboard_url(month), "error": f"{type(e).__name__}: {e}"}
        month_rows.append(row)

    unique_symbols = sorted({c["symbol"] for m in month_rows for c in m["weights"].get("constituents", [])})
    schema_symbols = {"RELIANCE", "HDFCBANK", "ICICIBANK", "TCS", "INFY", "ITC", "LT", "SBIN"}
    financial_coverage = [probe_financial_api(session, s, include_schema=s in schema_symbols) for s in unique_symbols]
    corporate_action_coverage = [probe_corporate_actions_api(session, s) for s in unique_symbols]

    holdout_values_present = any(
        x["tranche"] == "holdout" and any(k in x["official_target"] for k in ("pe", "pb", "dividend_yield_pct"))
        for x in month_rows
    )
    result = {
        "schema_version": 3,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "policy_id": policy["policy_id"], "research_only": True,
        "live_model_changed": False, "live_allocation_changed": False,
        "purpose": "Source-harvest stage for blinded recent-regime current-definition reconstruction.",
        "months": month_rows,
        "summary": {
            "months_total": len(month_rows),
            "development_months": sum(x["tranche"] == "development" for x in month_rows),
            "holdout_months": sum(x["tranche"] == "holdout" for x in month_rows),
            "development_targets_ok": dev_targets_ok,
            "weight_snapshots_strict_ok": weights_ok,
            "parsed_symbol_rows": parsed_symbol_rows,
            "symbol_rows_possible": 50 * len(month_rows),
            "unique_historical_symbols": len(unique_symbols),
            "current_security_master_symbol_matches": current_master_symbol_matches,
            "financial_api_symbols_http_ok": sum(x.get("status") == "ok" for x in financial_coverage),
            "financial_api_symbols_with_records": sum(x.get("has_records") for x in financial_coverage),
            "corporate_action_symbols_http_ok": sum(x.get("status") == "ok" for x in corporate_action_coverage),
            "corporate_action_symbols_with_records": sum(x.get("has_records") for x in corporate_action_coverage),
            "holdout_target_values_present": holdout_values_present,
        },
        "security_master": security_master_status,
        "unique_historical_symbols": unique_symbols,
        "financial_api_coverage": financial_coverage,
        "corporate_action_api_coverage": corporate_action_coverage,
        "holdout_guardrail": "Holdout official target values were not requested by this script and must remain absent until the reconstruction implementation is frozen.",
        "interpretation_guardrail": "Source accessibility and parser coverage are not reconstruction accuracy. The official weight PDF's index market-cap field is an adjusted index contribution, not by itself a substitute for the full-company market-cap basis required to combine unadjusted company earnings/book/dividends. This artifact cannot strengthen the timing-efficacy verdict or change V3.13.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    DEBUG.write_text("\n\n".join(debug_chunks) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    return result


if __name__ == "__main__":
    build()
