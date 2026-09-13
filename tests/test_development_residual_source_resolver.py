from pathlib import Path
import importlib.util
import json
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("resolver", ROOT / "scripts" / "development_residual_source_resolver_v12.py")
resolver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resolver)
POLICY = json.loads((ROOT / "development_residual_source_policy_v1.json").read_text())


def test_aliases_are_frozen_to_official_identity_changes():
    assert resolver.v1.ALIASES == {"LTIM": "LTM", "TATAMOTORS": "TMPV"}
    ltim = POLICY["identity_aliases"]["LTIM"]
    tata = POLICY["identity_aliases"]["TATAMOTORS"]
    assert ltim["continuity_isin"] == "INE214T01019"
    assert ltim["official_symbol_reference"] == "NSE/CML/72948 dated 2026-02-23"
    assert "2026-02-27" in ltim["reason"]
    assert tata["continuity_isin"] == "INE155A01022"
    assert tata["official_symbol_reference"] == "NSE/FAOP/70882 dated 2025-10-17"
    assert "same continuing listed security" in POLICY["identity_alias_rule"]


def test_financial_result_filter_is_narrow():
    assert resolver.v11.financial_result_like({"desc": "Financial Result Updates", "attchmntText": "period ended June 30, 2023"})
    assert resolver.v11.financial_result_like({"desc": "Outcome of Board Meeting", "attchmntText": "approved financial statements for period ended September 2022"})
    assert not resolver.v11.financial_result_like({"desc": "Closure of trading window", "attchmntText": "until dissemination of financial results for quarter ended September 30, 2022"})
    assert not resolver.v11.financial_result_like({"desc": "Press Release", "attchmntText": "financial results H1 FY24"})


def test_metadata_period_end_uses_exact_official_statement():
    r={"desc":"Financial Result Updates","attchmntText":"Company submitted financial results for the period ended June 30, 2023."}
    assert str(resolver.v11.metadata_period_end(r).date()) == "2023-06-30"
    r={"desc":"Outcome of Board Meeting","attchmntText":"financial statements for the period ended September 2022"}
    assert str(resolver.v11.metadata_period_end(r).date()) == "2022-09-30"


def test_metadata_period_end_rejects_non_quarter_month_only():
    r={"desc":"Outcome of Board Meeting","attchmntText":"financial statements for the period ended August 2023"}
    assert resolver.v11.metadata_period_end(r) is None


def test_audited_indicator_does_not_misread_unaudited():
    assert resolver.v1._audited_indicator("Consolidated AUDITED financial results")
    assert not resolver.v1._audited_indicator("Consolidated UNAUDITED financial results")


def test_pdf_period_parser_remains_fallback():
    text = "Statement of results for quarter and six months ended 30 September 2023 comparative 30 September 2022 and year ended 31 March 2023"
    ts = pd.Timestamp("2023-10-18 16:00")
    assert str(resolver.v1.current_period_end_from_pdf(text, ts).date()) == "2023-09-30"


def test_nestle_issuer_source_set_is_frozen_and_narrow():
    n = POLICY["nestle_issuer_fallback"]
    assert n["allowed_host"] == "www.nestle.in"
    assert "NESTLEIND" in n["scope"]
    rows = n["sources"]
    assert [r["period_end"] for r in rows] == [
        "2022-09-30", "2022-12-31", "2023-03-31",
        "2023-06-30", "2023-09-30", "2023-12-31",
    ]
    assert [r["audited_annual"] for r in rows] == [False, True, False, False, False, False]
    assert all(r["url"].startswith("https://www.nestle.in/") for r in rows)
    assert "31-Dec-2022" in n["annual_book_rule"]
    assert "31-Dec-2023" in n["annual_book_rule"] and "unaudited" in n["annual_book_rule"]


def test_nestle_period_visibility_is_explicit():
    assert resolver._period_visible("quarter ended 30 September 2023", "2023-09-30")
    assert resolver._period_visible("31.12.2023", "2023-12-31")
    assert not resolver._period_visible("quarter ended 30 June 2023", "2023-09-30")


def test_policy_revision_is_source_driven_and_zero_authority():
    assert POLICY["policy_id"] == "development-residual-source-resolver-v1.2"
    assert "first-party Nestle India investor disclosures" in POLICY["revision_reason"]
    assert POLICY["research_only"] is True
    assert POLICY["live_authority"] == "none"
    assert POLICY["promotion_effect"] == "none"
    assert "No Nifty dashboard" in POLICY["holdout_guardrail"]
