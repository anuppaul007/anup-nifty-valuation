#!/usr/bin/env python3
"""Inventory exact XBRL fact names used by the six development months.

Research only; zero live authority. This deliberately performs no NIFTY ratio
reconstruction and never fetches a holdout target. It reuses the frozen
Stage-B point-in-time source selection, downloads only the selected official NSE
XBRL filings for source-complete development constituents, hashes them, and
records candidate accounting facts for a later explicit tag-mapping policy.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

from lxml import etree
import requests

import development_accounting_source_map as source_map

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "development_xbrl_tag_inventory.json"
UA = source_map.UA

FAMILY_PATTERNS = {
    "profit": [
        r"profit.*loss.*attributable.*owners",
        r"profit.*attributable.*owners",
        r"profit.*loss.*period",
        r"netprofit",
        r"profitloss",
    ],
    "net_worth_or_equity": [
        r"networth",
        r"equity.*attributable.*owners",
        r"totalequity",
        r"shareholder.*fund",
    ],
    "bank_equity_structure": [
        r"^capital$",
        r"capital.*liabilit",
        r"reserve",
        r"shareholder.*fund",
    ],
    "share_capital": [
        r"paidup.*equity.*share.*capital",
        r"equity.*share.*capital",
        r"paidup.*capital",
    ],
    "face_value": [r"face.*value"],
    "eps": [r"earnings.*per.*share", r"basic.*eps", r"diluted.*eps"],
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text).lower())


def _local(tag: str) -> str:
    try:
        return etree.QName(tag).localname
    except Exception:
        return str(tag)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _valid_xbrl_url(url: str | None) -> bool:
    return isinstance(url, str) and url.startswith("https://nsearchives.nseindia.com/") and url.lower().endswith(".xml")


def _template_family(url: str | None) -> str:
    upper = str(url or "").upper()
    if "BANKING_" in upper:
        return "BANKING"
    if "INDAS_" in upper:
        return "INDAS"
    if "NBFC_" in upper:
        return "NBFC"
    if "INSURANCE_" in upper or "_LI_" in upper:
        return "LIFE_INSURANCE"
    if "_GI_" in upper:
        return "GENERAL_INSURANCE"
    return "OTHER"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({**UA, "Accept": "application/xml,text/xml,*/*"})
    return s


def _download(session: requests.Session, url: str, attempts: int = 3) -> bytes:
    last = None
    for i in range(attempts):
        try:
            r = session.get(url, timeout=25, headers={**UA, "Referer": "https://www.nseindia.com/"})
            r.raise_for_status()
            raw = r.content
            if not raw or b"<" not in raw[:500]:
                raise ValueError("response does not look like XML")
            return raw
        except Exception as e:
            last = e
            time.sleep(0.35 * (i + 1))
    raise RuntimeError(f"XBRL download failed after {attempts} attempts: {type(last).__name__}: {last}")


def _context_map(root: etree._Element) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for elem in root.iter():
        if _local(elem.tag).lower() != "context":
            continue
        cid = elem.get("id")
        if not cid:
            continue
        rec: dict[str, object] = {"id": cid}
        start = end = instant = None
        dims = []
        for child in elem.iter():
            name = _local(child.tag).lower()
            txt = (child.text or "").strip()
            if name == "startdate":
                start = txt
            elif name == "enddate":
                end = txt
            elif name == "instant":
                instant = txt
            elif name in {"explicitmember", "typedmember"}:
                dims.append({"dimension": child.get("dimension"), "value": txt})
        if instant:
            rec["instant"] = instant
        if start or end:
            rec["start_date"] = start
            rec["end_date"] = end
        if dims:
            rec["dimensions"] = dims
        out[cid] = rec
    return out


def _candidate_family(local_name: str) -> list[str]:
    key = _norm(local_name)
    out = []
    for family, patterns in FAMILY_PATTERNS.items():
        if any(re.search(p, key) for p in patterns):
            out.append(family)
    return out


def inspect_xbrl(raw: bytes) -> dict:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True, recover=False)
    root = etree.fromstring(raw, parser=parser)
    contexts = _context_map(root)
    namespaces = {str(k or "default"): str(v) for k, v in (root.nsmap or {}).items()}
    fact_name_counts: dict[str, int] = {}
    families: dict[str, list[dict]] = {k: [] for k in FAMILY_PATTERNS}
    numeric_fact_count = 0

    for elem in root.iter():
        if len(elem):
            continue
        context_ref = elem.get("contextRef")
        if not context_ref:
            continue
        raw_text = (elem.text or "").strip()
        if not raw_text:
            continue
        local_name = _local(elem.tag)
        fact_name_counts[local_name] = fact_name_counts.get(local_name, 0) + 1
        compact = raw_text.replace(",", "").replace("(", "-").replace(")", "")
        try:
            float(compact)
            numeric_fact_count += 1
        except Exception:
            pass
        matched = _candidate_family(local_name)
        if not matched:
            continue
        rec = {
            "local_name": local_name,
            "context_ref": context_ref,
            "context": contexts.get(context_ref),
            "unit_ref": elem.get("unitRef"),
            "decimals": elem.get("decimals"),
            "scale": elem.get("scale"),
            "sign": elem.get("sign"),
            "value": raw_text,
        }
        for family in matched:
            if len(families[family]) < 120:
                families[family].append(rec)

    return {
        "root_local_name": _local(root.tag),
        "namespaces": namespaces,
        "contexts": len(contexts),
        "fact_name_count": len(fact_name_counts),
        "numeric_fact_count": numeric_fact_count,
        "top_fact_names": sorted(fact_name_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:120],
        "candidate_facts": families,
        "candidate_family_counts": {k: len(v) for k, v in families.items()},
    }


def selected_sources(stage_b: dict) -> tuple[list[dict], list[dict]]:
    gap_pairs = {(g["month"], g["symbol"]) for g in stage_b["gaps"]}
    by_url: dict[str, dict] = {}
    invalid = []
    for snap in stage_b["development_snapshots"]:
        month = snap["month"]
        for company in snap["companies"]:
            symbol = company["symbol"]
            if (month, symbol) in gap_pairs:
                continue
            records = list(company["ttm_source_chain"].get("records", []))
            annual = company.get("annual_book_source", {}).get("record")
            if annual:
                records.append(annual)
            for rec in records:
                url = rec.get("xbrl")
                if not _valid_xbrl_url(url):
                    invalid.append({"month": month, "symbol": symbol, "xbrl": url, "period_end": rec.get("period_end")})
                    continue
                key = str(url)
                entry = by_url.setdefault(key, {
                    "url": key,
                    "uses": [],
                    "stage_b_template_hint": rec.get("template"),
                    "template_family": _template_family(key),
                })
                use = {"month": month, "symbol": symbol, "period_end": rec.get("period_end"), "source_period": rec.get("period")}
                if use not in entry["uses"]:
                    entry["uses"].append(use)
    return sorted(by_url.values(), key=lambda x: x["url"]), invalid


def build() -> dict:
    stage_b = source_map.build()
    sources, invalid = selected_sources(stage_b)
    session = _session()
    inspected = []
    failures = []
    aggregate_localnames: dict[str, set[str]] = {k: set() for k in FAMILY_PATTERNS}

    for i, source in enumerate(sources, 1):
        url = source["url"]
        try:
            raw = _download(session, url)
            info = inspect_xbrl(raw)
            rec = {**source, "status": "ok", "sha256": _sha256(raw), "size_bytes": len(raw), **info}
            inspected.append(rec)
            for family, facts in info["candidate_facts"].items():
                aggregate_localnames[family].update(str(f["local_name"]) for f in facts)
        except Exception as e:
            failures.append({**source, "status": "unavailable", "error": f"{type(e).__name__}: {e}"})
        if i % 20 == 0:
            time.sleep(0.15)

    template_counts = Counter(x["template_family"] for x in sources)
    result = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "research_only": True,
        "live_authority": "none",
        "live_model_changed": False,
        "live_allocation_changed": False,
        "holdout_target_fetch_count": 0,
        "ratios_computed": False,
        "purpose": "Development-only inventory of exact NSE XBRL fact names before freezing any numerical accounting tag map.",
        "stage_b_summary": stage_b["summary"],
        "stage_b_gap_symbols": sorted({g["symbol"] for g in stage_b["gaps"]}),
        "selected_sources": len(sources),
        "template_family_counts": dict(sorted(template_counts.items())),
        "invalid_selected_xbrl_links": invalid,
        "xbrl_files_ok": len(inspected),
        "xbrl_files_failed": len(failures),
        "candidate_local_names": {k: sorted(v) for k, v in aggregate_localnames.items()},
        "files": inspected,
        "failures": failures,
        "interpretation_guardrail": "Candidate fact names are discovery evidence only. Bank capital/reserve facts are inventoried separately because generic IndAS equity labels are not assumed to define bank P/B. No candidate is authorized as the official earnings, net-worth, share-capital, face-value or EPS mapping until a separate frozen mapping policy and tests are reviewed. No NIFTY ratio is computed here.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "selected_sources": result["selected_sources"],
        "template_family_counts": result["template_family_counts"],
        "xbrl_files_ok": result["xbrl_files_ok"],
        "xbrl_files_failed": result["xbrl_files_failed"],
        "invalid_selected_xbrl_links": len(invalid),
        "stage_b_gap_symbols": result["stage_b_gap_symbols"],
        "candidate_name_counts": {k: len(v) for k, v in result["candidate_local_names"].items()},
        "holdout_target_fetch_count": 0,
        "ratios_computed": False,
    }, indent=2))
    return result


if __name__ == "__main__":
    build()
