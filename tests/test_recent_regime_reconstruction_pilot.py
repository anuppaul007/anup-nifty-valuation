from pathlib import Path
import importlib.util
import json
import math

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pilot", ROOT / "scripts" / "recent_regime_reconstruction_pilot.py")
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)
POLICY = json.loads((ROOT / "recent_reconstruction_policy_v1.json").read_text())


def test_frozen_month_partition_is_6_plus_30():
    months = pilot.month_range("2023-09", "2026-08")
    assert len(months) == 36
    assert months[:6] == POLICY["sample"]["development_months"]
    assert months[6] == "2024-03" and months[-1] == "2026-08"


def test_holdout_target_fetch_is_blocked():
    assert pilot.target_fetch_allowed("2023-09", POLICY)
    assert pilot.target_fetch_allowed("2024-02", POLICY)
    assert not pilot.target_fetch_allowed("2024-03", POLICY)
    assert not pilot.target_fetch_allowed("2026-08", POLICY)


def test_dashboard_parser_uses_last_three_fields():
    text = "Nifty 50 2.00 2.67 16.06 21.87 13.77 10.15 1.00 1.00 1.00 22.21 3.45 1.37"
    x = pilot.parse_nifty50_dashboard(text)
    assert x["pe"] == 22.21
    assert x["pb"] == 3.45
    assert x["dividend_yield_pct"] == 1.37


def test_weight_parser_reads_symbol_close_mcap_weight():
    rows = ["Symbol Security Name Industry Close Price Index Mcap Weightage (%)"]
    for i in range(50):
        rows.append(f"SYM{i:02d} Company {i:02d} Industry Name 100.00 10000 2.00")
    parsed, d = pilot.parse_weight_table("\n".join(rows))
    assert d["strict_ok"] is True
    assert len(parsed) == 50
    assert math.isclose(d["weight_sum_pct"], 100.0)
    assert parsed[0]["symbol"] == "SYM00"
    assert parsed[0]["close_price"] == 100.0
    assert parsed[0]["index_mcap_crore"] == 10000.0
    assert parsed[0]["weight_pct"] == 2.0


def test_weight_parser_handles_wrapped_weight_on_previous_line():
    rows = ["Symbol Security Name Industry Close Price Index Mcap Weightage (%)"]
    rows += [" Long Security Name 2.00", "WRAP Industry Name 100.00 10000"]
    for i in range(49):
        rows.append(f"SYM{i:02d} Company {i:02d} Industry Name 100.00 10000 2.00")
    parsed, d = pilot.parse_weight_table("\n".join(rows))
    assert d["strict_ok"] is True
    assert len(parsed) == 50
    wrap = next(x for x in parsed if x["symbol"] == "WRAP")
    assert wrap["weight_pct"] == 2.0
    assert wrap["weight_source"] == "preceding_wrapped_line"
    assert d["wrapped_weight_rows"] == 1


def test_policy_has_no_live_authority_and_predeclares_tolerance():
    assert POLICY["research_only"] is True
    assert POLICY["live_authority"] == "none"
    assert POLICY["predeclared_holdout_tolerance"]["per_month_pe_relative_error_max_pct"] == 2.0
    assert POLICY["predeclared_holdout_tolerance"]["aggregate_months_all_three_within_tolerance_min"] == 27
    assert "new untouched holdout" in POLICY["failure_rule"]
