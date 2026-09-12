from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import protocol_backtest as p


def _s(vals, start="2020-01"):
    idx = pd.period_range(start, periods=len(vals), freq="M")
    return pd.Series(vals, index=idx, dtype=float)


def test_conservative_rate_never_exceeds_inputs():
    assert p.conservative_rate_pct(10.0, 8.0, 1.0) == 7.0
    assert p.conservative_rate_pct(0.5, 1.0, 1.0) == 0.0
    assert p.conservative_rate_pct(None, 6.0, 1.0) == 5.0


def test_zero_band_rebalances_to_each_new_target():
    target = _s([0.5, 0.6, 0.4])
    eq = _s([0.10, 0.00, 0.00])
    debt = _s([0.00, 0.00, 0.00])
    sim = p.simulate(target, eq, debt, band_pp=0, cost_bps=0)
    assert sim["rebalances"] == 2
    assert sim["one_way_turnover"] > 0


def test_band_avoids_small_rebalance_after_drift():
    target = _s([0.50, 0.51])
    eq = _s([0.01, 0.00])
    debt = _s([0.00, 0.00])
    sim = p.simulate(target, eq, debt, band_pp=5, cost_bps=10)
    assert sim["rebalances"] == 0
    assert sim["one_way_turnover"] == 0


def test_cost_uses_drift_to_target_turnover():
    target = _s([0.50, 0.50])
    eq = _s([0.20, 0.00])
    debt = _s([0.00, 0.00])
    no_cost = p.simulate(target, eq, debt, band_pp=0, cost_bps=0)
    with_cost = p.simulate(target, eq, debt, band_pp=0, cost_bps=100)
    assert no_cost["one_way_turnover"] > 0
    assert with_cost["ending_multiple"] < no_cost["ending_multiple"]


def test_cached_rate_series_is_not_silent_repo_series():
    rates = p.load_cached_short_rate()
    assert rates[pd.Period("2000-03", "M")] == 16.52
    assert p.RATE_AUDIT["cached_short_rate"]["not"] == "RBI policy repo rate"


def test_rbi_tbill_partial_series_not_used_as_full_history():
    audit = p.RATE_AUDIT["rbi_91d_tbill_check"]
    assert audit["status"] == "partial_verified_not_used_for_full_period"
    assert audit["verified_annual_weighted_average_cutoff_yields_pct"]["2002-03"] == 5.73
