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


def normalise_company_name(name: str) -> str:
    x = str(name).upper().replace("&", " AND ")
    x = re.sub(r"\bLIMITED\b|\bLTD\b|\bLTD\.\b", " ", x)
    x = re.sub(r"[^A-Z0-9]+", " ", x)
    return re.sub(r"\s+", " ", x).strip()


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


def parse_weight_table(text: str) -> tuple[list[dict], dict]:
    """Best-effort parser for the official monthly NIFTY 50 weight PDF.

    It deliberately fails closed unless exactly 50 plausible constituent rows
    are isolated and the displayed weights sum close to 100%.
    """
    lines = text.splitlines()
    header_idx = None
    for i, raw in enumerate(lines):
        low = raw.lower()
        if "weight" in low and ("company" in low or "constituent" in low or "security" in low):
            header_idx = i
            break
    scan = lines[header_idx + 1:] if header_idx is not None else lines
    candidates: list[dict] = []
    for raw in scan:
        stripped = raw.strip()
        low = stripped.lower()
        if not stripped:
            continue
        if any(k in low for k in ("sector representation", "industry representation", "disclaimer", "nse indices limited", "contact us")):
            if candidates:
                break
            continue
        m = re.search(r"\s([0-9]+(?:\.[0-9]+)?)\s*$", raw)
        if not m:
            continue
        weight = float(m.group(1))
        if not (0 < weight < 30):
            continue
        left = raw[:m.start()].rstrip()
        parts = [re.sub(r"\s+", " ", x).strip() for x in re.split(r"\s{2,}", left) if x.strip()]
        if not parts:
            continue
        company = parts[0]
        if len(company) < 2 or company.lower() in {"company", "company name", "constituent"}:
            continue
        candidates.append({"company": company, "weight_pct": weight, "raw": re.sub(r"\s+", " ", raw).strip()})
        if len(candidates) >= 50:
            # Some PDFs have additional sector tables after the constituent table.
            break
    total = sum(x["weight_pct"] for x in candidates)
    ok = len(candidates) == 50 and 98.5 <= total <= 101.5
    diagnostics = {
        "header_found": header_idx is not None,
        "candidate_rows": len(candidates),
        "weight_sum_pct": total,
        "strict_ok": ok,
    }
    return (candidates if ok else []), diagnostics


def parse_security_master(raw: bytes) -> dict[str, list[dict]]:
    text = raw.decode("utf-8", errors="replace").lstrip("\ufeff")
    reader = csv.DictReader(StringIO(text))
    out: dict[str, list[dict]] = {}
    for row in reader:
        symbol = (row.get("SYMBOL") or row.get("Symbol") or "").strip()
        company = (row.get("NAME OF COMPANY") or row.get("NAME_OF_COMPANY") or row.get("NAME") or "").strip()
        if not symbol or not company:
            continue
        out.setdefault(normalise_company_name(company), []).append({"symbol": symbol, "company": company})
    return out


def map_weights_to_symbols(rows: list[dict], security_master: dict[str, list[dict]]) -> tuple[list[dict], list[str]]:
    mapped = []
    unresolved = []
    for row in rows:
        matches = security_master.get(normalise_company_name(row["company"]), [])
        if len(matches) == 1:
            mapped.append({**row, "symbol": matches[0]["symbol"], "symbol_match": "exact_normalised_company_name"})
        else:
            mapped.append({**row, "symbol": None, "symbol_match": "unresolved"})
            unresolved.append(row["company"])
    return mapped, unresolved


def probe_financial_api_schema(session: requests.Session, symbol: str) -> dict:
    url = "https://www.nseindia.com/api/corporates-financial-results"
    try:
        r = session.get(url, params={"index": "equities", "symbol": symbol, "period": "Quarterly"}, timeout=20,
                        headers={**UA, "Accept": "application/json,text/plain,*/*", "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-financial-results"})
        r.raise_for_status()
        data = r.json()
        records = data if isinstance(data, list) else (data.get("data") if isinstance(data, dict) else [])
        records = records if isinstance(records, list) else []
        sample = records[0] if records else {}
        keys = sorted(str(k) for k in sample.keys()) if isinstance(sample, dict) else []
        link_keys = sorted(k for k in keys if any(t in k.lower() for t in ("xbrl", "link", "url", "file")))
        date_keys = sorted(k for k in keys if any(t in k.lower() for t in ("date", "time")))
        return {"symbol": symbol, "status": "ok", "records": len(records), "keys": keys, "link_keys": link_keys, "date_keys": date_keys}
    except Exception as e:
        return {"symbol": symbol, "status": "unavailable", "error": f"{type(e).__name__}: {e}"}


def build() -> dict:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    months = month_range(policy["sample"]["start_month"], policy["sample"]["end_month"])
    if len(months) != policy["sample"]["completed_months"]:
        raise RuntimeError("policy month count mismatch")

    session = _session()
    security_master_url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    security_master = {}
    security_master_status = {"status": "unavailable"}
    try:
        raw_master = _get_bytes(session, security_master_url)
        security_master = parse_security_master(raw_master)
        security_master_status = {"status": "ok", "rows_normalised": len(security_master), "sha256": sha256_bytes(raw_master), "url": security_master_url}
    except Exception as e:
        security_master_status = {"status": "unavailable", "error": f"{type(e).__name__}: {e}", "url": security_master_url}

    month_rows = []
    debug_chunks = []
    dev_targets_ok = 0
    weights_ok = 0
    mapped_total = 0
    mapped_possible = 0

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
            mapped, unresolved = map_weights_to_symbols(parsed, security_master) if parsed and security_master else (parsed, [x["company"] for x in parsed])
            row["weights"] = {
                "url": weights_zip_url(month),
                "status": "ok" if parsed else "unparsed",
                "zip_sha256": sha256_bytes(zip_raw),
                "pdf_member": member,
                "pdf_sha256": sha256_bytes(pdf_raw),
                "diagnostics": diagnostics,
                "constituents": mapped,
                "symbol_exact_matches": sum(1 for x in mapped if x.get("symbol")),
                "unresolved_company_names": unresolved,
            }
            if parsed:
                weights_ok += 1
                mapped_total += sum(1 for x in mapped if x.get("symbol"))
                mapped_possible += len(mapped)
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

    probe_symbols = ["RELIANCE", "HDFCBANK", "ICICIBANK", "TCS", "INFY", "ITC", "LT", "SBIN"]
    schema_probes = [probe_financial_api_schema(session, s) for s in probe_symbols]

    holdout_values_present = any(
        x["tranche"] == "holdout" and any(k in x["official_target"] for k in ("pe", "pb", "dividend_yield_pct"))
        for x in month_rows
    )
    result = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "policy_id": policy["policy_id"],
        "research_only": True,
        "live_model_changed": False,
        "live_allocation_changed": False,
        "purpose": "Source-harvest stage for blinded recent-regime current-definition reconstruction.",
        "months": month_rows,
        "summary": {
            "months_total": len(month_rows),
            "development_months": sum(x["tranche"] == "development" for x in month_rows),
            "holdout_months": sum(x["tranche"] == "holdout" for x in month_rows),
            "development_targets_ok": dev_targets_ok,
            "weight_snapshots_strict_ok": weights_ok,
            "symbol_exact_matches": mapped_total,
            "symbol_rows_possible": mapped_possible,
            "holdout_target_values_present": holdout_values_present,
        },
        "security_master": security_master_status,
        "financial_api_schema_probes": schema_probes,
        "holdout_guardrail": "Holdout official target values were not requested by this script and must remain absent until the reconstruction implementation is frozen.",
        "interpretation_guardrail": "Source accessibility and parser coverage are not reconstruction accuracy. This artifact cannot strengthen the timing-efficacy verdict or change V3.13.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    DEBUG.write_text("\n\n".join(debug_chunks) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    return result


if __name__ == "__main__":
    build()
