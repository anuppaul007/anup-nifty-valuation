#!/usr/bin/env python3
"""Independent, fail-closed source-identity and date-only PIT guard for Nestle development evidence.

This is a research guard, NOT a certification of the underlying issuer PDF
bytes or a replacement for actual exchange signal timestamps. The 30-month
holdout is never accessed and no live allocation code is imported.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date
import json
from pathlib import Path

from development_manual_evidence import validate_nestle_evidence

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "development_manual_evidence" / "nestleind_v1.json"
SOURCE_POLICY = ROOT / "development_residual_source_policy_v1.json"
RECON_POLICY = ROOT / "recent_reconstruction_policy_v1.json"

# Independent immutable-in-code cross-check. Changes to either JSON file
# alone cannot silently move a publication date or substitute a source URL.
FROZEN = (
    ("2022-09-30", "2022-10-19", "nestle-q3-2022", "https://www.nestle.in/sites/g/files/pydnoa451/files/2022-10/Outcome%20of%20Board%20Meeting_19.10.2022.pdf", False),
    ("2022-12-31", "2023-02-16", "nestle-fy2022-q4", "https://www.nestle.in/sites/g/files/pydnoa451/files/2023-02/Outcome-Board-Meeting-result.pdf", True),
    ("2023-03-31", "2023-04-25", "nestle-q1-2023", "https://www.nestle.in/sites/g/files/pydnoa451/files/2023-04/BSEOutcomeofBM25042023Signed.pdf", False),
    ("2023-06-30", "2023-07-27", "nestle-q2-2023", "https://www.nestle.in/sites/g/files/pydnoa451/files/2023-07/BSE_Intimation_27072023_signed-v1.pdf", False),
    ("2023-09-30", "2023-10-19", "nestle-q3-2023", "https://www.nestle.in/sites/g/files/pydnoa451/files/2023-10/BSENSE19102023signed-v2.pdf", False),
    ("2023-12-31", "2024-02-07", "nestle-q4-2023", "https://www.nestle.in/sites/g/files/pydnoa451/files/2024-02/Stock%20Exchange%20Intimation%20BSE%26amp%3B%20NSE%2007.02.2024.pdf", False),
)
DEVELOPMENT = ("2023-09", "2023-10", "2023-11", "2023-12", "2024-01", "2024-02")


class SourceIntegrityError(ValueError):
    pass


def _cutoff_bound(month: str) -> date:
    year, mm = map(int, month.split("-"))
    return date(year, mm, monthrange(year, mm)[1])


def _source_tuple(row: dict, *, evidence: bool) -> tuple:
    return (
        row["period_end"],
        row["publication_date"],
        row["source_id"],
        row["source_url"] if evidence else row["url"],
        bool(row.get("audited_annual", False)),
    )


def validate_nestle_source_integrity(
    evidence_path: Path = EVIDENCE,
    source_policy_path: Path = SOURCE_POLICY,
    recon_policy_path: Path = RECON_POLICY,
) -> dict:
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    policy = json.loads(source_policy_path.read_text(encoding="utf-8"))
    recon = json.loads(recon_policy_path.read_text(encoding="utf-8"))
    if tuple(recon["sample"]["development_months"]) != DEVELOPMENT:
        raise SourceIntegrityError("frozen development window changed")
    if recon["sample"]["holdout_start"] != "2024-03":
        raise SourceIntegrityError("holdout boundary changed")
    if evidence.get("holdout_target_fetch_count") != 0 or evidence.get("live_authority") != "none":
        raise SourceIntegrityError("manual evidence lost its sealed/zero-authority status")
    if policy.get("live_authority") != "none" or policy.get("research_only") is not True:
        raise SourceIntegrityError("source policy lost research-only status")

    issuer = policy["nestle_issuer_fallback"]
    source_rows = issuer["sources"]
    evidence_rows = evidence["quarter_facts"]
    if len(source_rows) != len(FROZEN) or len(evidence_rows) != len(FROZEN):
        raise SourceIntegrityError("source count changed")
    if tuple(_source_tuple(row, evidence=False) for row in source_rows) != FROZEN:
        raise SourceIntegrityError("source-policy identity, publication date or audit flag drifted")
    if tuple(_source_tuple(row, evidence=True) for row in evidence_rows) != FROZEN:
        raise SourceIntegrityError("manual evidence identity, publication date or audit flag drifted")
    if len({row["source_id"] for row in evidence_rows}) != len(FROZEN):
        raise SourceIntegrityError("duplicate source identifier")

    by_period = {row["period_end"]: row for row in evidence_rows}
    observed_chains = {}
    for month in DEVELOPMENT:
        # Date-only upper bound is necessary, not sufficient: exact exchange
        # trading-day signal timestamps must still be verified later.
        bound = _cutoff_bound(month)
        eligible = sorted(
            (row for row in evidence_rows
             if date.fromisoformat(row["publication_date"]) < bound),
            key=lambda row: row["period_end"],
        )
        if len(eligible) < 4:
            raise SourceIntegrityError("insufficient PIT quarters for " + month)
        selected = eligible[-4:]
        ends = [row["period_end"] for row in selected]
        if month == "2023-09" and "2023-09-30" in ends:
            raise SourceIntegrityError("September 2023 result leaked into September signal")
        if month == "2024-01" and "2023-12-31" in ends:
            raise SourceIntegrityError("February 2024 publication leaked into January signal")
        expected_ttm = round(sum(float(row["profit_for_period"]) for row in selected), 1)
        actual_ttm = round(float(evidence["ttm_profit_by_development_month"][month]), 1)
        if expected_ttm != actual_ttm:
            raise SourceIntegrityError("PIT quarter-chain arithmetic mismatch for " + month)
        audited = [
            row for row in eligible
            if row.get("audited_annual") is True
        ]
        if not audited or audited[-1]["period_end"] != evidence["annual_book_rule"]["eligible_annual_period_end"]:
            raise SourceIntegrityError("audited annual book source is not PIT eligible")
        observed_chains[month] = ends

    validate_nestle_evidence(evidence_path)
    if evidence.get("machine_reproducible_source_retrieval") is not False:
        raise SourceIntegrityError("manual source evidence cannot claim machine retrieval")
    if not str(evidence.get("dividend_evidence_status", "")).startswith("not_frozen_here"):
        raise SourceIntegrityError("dividend evidence status changed without independent verification")
    return {
        "status": "source_identity_and_date_bound_guard_pass",
        "development_months_checked": list(DEVELOPMENT),
        "quarter_source_identities_checked": len(FROZEN),
        "pit_quarter_chains": observed_chains,
        "issuer_pdf_bytes_hash_verified": False,
        "exact_trading_signal_cutoffs_verified": False,
        "dividend_evidence_complete": False,
        "full_numerical_development_milestone_complete": False,
        "holdout_target_fetch_count": 0,
        "live_authority": "none",
    }


if __name__ == "__main__":
    print(json.dumps(validate_nestle_source_integrity(), indent=2))
