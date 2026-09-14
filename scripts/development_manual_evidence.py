#!/usr/bin/env python3
"""Validate controlled manual evidence bridges used only in development research.

This module does not fetch holdout targets and does not upgrade a manual bridge
to machine-reproducible source retrieval. It exists so exceptional first-party
sources blocked in CI can still be represented transparently, with arithmetic
and corporate-action continuity tested before later use.
"""
from __future__ import annotations

import json
from pathlib import Path

from development_accounting_semantics import validate_four_quarter_chain

ROOT = Path(__file__).resolve().parents[1]
NESTLE_PATH = ROOT / "development_manual_evidence" / "nestleind_v1.json"


class ManualEvidenceError(ValueError):
    pass


def validate_nestle_evidence(path: Path = NESTLE_PATH) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    if d.get("research_only") is not True or d.get("live_authority") != "none":
        raise ManualEvidenceError("manual evidence acquired live authority")
    if d.get("holdout_target_fetch_count") != 0:
        raise ManualEvidenceError("manual evidence reports holdout access")
    if d.get("machine_reproducible_source_retrieval") is not False:
        raise ManualEvidenceError("manual evidence may not masquerade as machine-reproducible retrieval")
    if d.get("controlled_manual_evidence") is not True:
        raise ManualEvidenceError("manual evidence marker missing")

    quarters = d.get("quarter_facts") or []
    if [q.get("period_end") for q in quarters] != [
        "2022-09-30", "2022-12-31", "2023-03-31",
        "2023-06-30", "2023-09-30", "2023-12-31",
    ]:
        raise ManualEvidenceError("Nestle quarter sequence changed")
    for q in quarters:
        if not str(q.get("source_url", "")).startswith("https://www.nestle.in/"):
            raise ManualEvidenceError("Nestle evidence must remain first-party")
        if float(q["paid_up_equity_capital"]) != 964.2:
            raise ManualEvidenceError("unexpected paid-up capital")
        implied = round(float(q["paid_up_equity_capital"]) * 1_000_000 / float(q["face_value_rupees"]))
        if implied != int(q["shares_outstanding"]):
            raise ManualEvidenceError(f"share-count reconciliation failed for {q['period_end']}")

    action = (d.get("corporate_actions") or [None])[0]
    if not action or action.get("action") != "share_split":
        raise ManualEvidenceError("share split evidence missing")
    if action.get("effective_date") != "2024-01-05" or action.get("ratio_old_to_new") != "1:10":
        raise ManualEvidenceError("share split terms changed")
    if int(action["new_shares"]) != int(action["old_shares"]) * 10:
        raise ManualEvidenceError("share split arithmetic inconsistent")

    profit = {q["period_end"]: float(q["profit_for_period"]) for q in quarters}
    chains = {
        "2023-09": ["2022-09-30", "2022-12-31", "2023-03-31", "2023-06-30"],
        "2023-10": ["2022-12-31", "2023-03-31", "2023-06-30", "2023-09-30"],
        "2023-11": ["2022-12-31", "2023-03-31", "2023-06-30", "2023-09-30"],
        "2023-12": ["2022-12-31", "2023-03-31", "2023-06-30", "2023-09-30"],
        "2024-01": ["2022-12-31", "2023-03-31", "2023-06-30", "2023-09-30"],
        "2024-02": ["2023-03-31", "2023-06-30", "2023-09-30", "2023-12-31"],
    }
    frozen_ttm = d.get("ttm_profit_by_development_month") or {}
    for month, ends in chains.items():
        validate_four_quarter_chain(ends)
        calc = round(sum(profit[e] for e in ends), 1)
        if calc != round(float(frozen_ttm[month]), 1):
            raise ManualEvidenceError(f"TTM mismatch for {month}: {calc} != {frozen_ttm[month]}")

    annual = d.get("annual_book_rule") or {}
    if annual.get("eligible_annual_period_end") != "2022-12-31":
        raise ManualEvidenceError("annual book source changed")
    fy = next(q for q in quarters if q["period_end"] == "2022-12-31")
    if round(float(fy["annual_equity_share_capital"]) + float(fy["annual_other_equity"]), 1) != round(float(fy["annual_total_equity"]), 1):
        raise ManualEvidenceError("annual equity components do not reconcile")
    if round(float(annual["eligible_total_equity"]), 1) != round(float(fy["annual_total_equity"]), 1):
        raise ManualEvidenceError("annual book rule does not match audited source fact")

    if not str(d.get("dividend_evidence_status", "")).startswith("not_frozen_here"):
        raise ManualEvidenceError("dividend evidence must remain explicitly unresolved in v1")

    return {
        "evidence_id": d["evidence_id"],
        "quarters": len(quarters),
        "development_ttm_months": len(chains),
        "share_split_reconciled": True,
        "annual_book_reconciled": True,
        "dividend_evidence_complete": False,
        "machine_reproducible_source_retrieval": False,
        "holdout_target_fetch_count": 0,
        "live_authority": "none",
    }


if __name__ == "__main__":
    print(json.dumps(validate_nestle_evidence(), indent=2))
