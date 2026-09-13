from pathlib import Path
import importlib.util
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("resolver", ROOT / "scripts" / "development_residual_source_resolver.py")
resolver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resolver)
POLICY = json.loads((ROOT / "development_residual_source_policy_v1.json").read_text())


def test_aliases_are_frozen_to_official_identity_changes():
    assert resolver.ALIASES == {"LTIM": "LTM", "TATAMOTORS": "TMPV"}


def test_financial_result_filter_is_narrow():
    assert resolver._financial_result_like({"desc": "Financial Results", "attchmntText": "Quarter ended"})
    assert resolver._financial_result_like({"desc": "Outcome of Board Meeting", "attchmntText": "approved financial results"})
    assert not resolver._financial_result_like({"desc": "Investor Presentation", "attchmntText": "strategy update"})


def test_audited_indicator_does_not_misread_unaudited():
    assert resolver._audited_indicator("Consolidated AUDITED financial results")
    assert not resolver._audited_indicator("Consolidated UNAUDITED financial results")


def test_period_parser_chooses_latest_recent_quarter_end():
    text = "Statement of results for quarter and six months ended 30 September 2023 comparative 30 September 2022 and year ended 31 March 2023"
    ts = pd.Timestamp("2023-10-18 16:00")
    assert str(resolver.current_period_end_from_pdf(text, ts).date()) == "2023-09-30"


def test_old_comparative_dates_do_not_become_current_period():
    text = "Results for quarter ended 30 June 2023; comparative 30 June 2022; year ended 31 March 2023"
    ts = pd.Timestamp("2023-07-15 17:00")
    assert str(resolver.current_period_end_from_pdf(text, ts).date()) == "2023-06-30"


def test_policy_has_zero_authority_and_no_holdout_permission():
    assert POLICY["research_only"] is True
    assert POLICY["live_authority"] == "none"
    assert POLICY["promotion_effect"] == "none"
    assert "No Nifty dashboard" in POLICY["holdout_guardrail"]
