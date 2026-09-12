from pathlib import Path
import importlib.util
import math

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "cdr", ROOT / "scripts" / "current_definition_reconstruction.py"
)
cdr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cdr)


def test_normalize_percent_weights():
    w = cdr.normalize_weights([40, 35, 25])
    assert math.isclose(float(w.sum()), 1.0, abs_tol=1e-12)
    assert math.isclose(float(w.iloc[0]), 0.40, abs_tol=1e-12)


def test_reject_incomplete_weights():
    try:
        cdr.normalize_weights([0.4, 0.35, 0.10])
        assert False, "should reject 85% weight coverage"
    except ValueError as e:
        assert "incomplete" in str(e)


def test_index_ratio_aggregation_identity():
    # Two equal-weight companies. Harmonic aggregation applies to PE/PB;
    # dividend yield is the arithmetic weighted average.
    x = cdr.aggregate_current_definition(
        [50, 50], pe=[10, 20], pb=[2, 4], dividend_yield_pct=[1, 3]
    )
    assert math.isclose(x["pe"], 13.333333333333334, rel_tol=1e-12)
    assert math.isclose(x["pb"], 2.6666666666666665, rel_tol=1e-12)
    assert math.isclose(x["dividend_yield_pct"], 2.0, rel_tol=1e-12)


def test_company_input_conversion():
    x = cdr.current_definition_company_inputs(
        market_cap=1000, ttm_earnings=50, book_value=250, rolling_12m_dividends=20
    )
    assert x == {"pe": 20.0, "pb": 4.0, "dividend_yield_pct": 2.0}


def test_point_in_time_gate():
    assert cdr.point_in_time_eligible("2024-04-15 15:00", "2024-05-01")
    assert not cdr.point_in_time_eligible("2024-05-05", "2024-05-01")


def _rows(n=50):
    return [
        {
            "weight": 2.0,
            "pe": 20.0,
            "pb": 4.0,
            "dividend_yield_pct": 1.5,
            "filing_ok": True,
            "dividend_history_ok": True,
        }
        for _ in range(n)
    ]


def test_month_reconstructable_requires_all_50():
    ok, why = cdr.month_reconstructable(_rows(50))
    assert ok and why == "complete"
    ok, why = cdr.month_reconstructable(_rows(49))
    assert not ok and "member_count" in why


def test_month_reconstructable_fails_late_filing():
    rows = _rows(50)
    rows[3]["filing_ok"] = False
    ok, why = cdr.month_reconstructable(rows)
    assert not ok and why == "filing_not_point_in_time"


def test_month_reconstructable_fails_missing_dividend_history():
    rows = _rows(50)
    rows[7]["dividend_history_ok"] = False
    ok, why = cdr.month_reconstructable(rows)
    assert not ok and why == "dividend_history_incomplete"


def test_research_script_has_no_live_writes():
    text = (ROOT / "scripts" / "current_definition_reconstruction.py").read_text()
    assert "model.js" in text and "live_model_changed" in text
    assert "latest.json" in text
    assert "OUT = ROOT / \"data\" / \"current_definition_reconstruction.json\"" in text
