import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import current_definition_aggregation as a


def test_positive_case_matches_harmonic_identity():
    x = a.aggregate_from_point_in_time_inputs(
        weights=[50, 50],
        market_cap=[1000, 1000],
        ttm_earnings=[100, 50],
        book_value=[500, 250],
        rolling_12m_dividends=[10, 30],
    )
    assert math.isclose(x['pe'], 13.333333333333334, rel_tol=1e-12)
    assert math.isclose(x['pb'], 2.6666666666666665, rel_tol=1e-12)
    assert math.isclose(x['dividend_yield_pct'], 2.0, rel_tol=1e-12)


def test_loss_making_constituent_is_included_not_rejected():
    # Equal market-cap bases and equal index weights. The second company loses
    # 20 while the first earns 100, so aggregate earnings yield is 4% and index
    # PE is 25. Dropping the loss-maker would incorrectly report PE=20.
    x = a.aggregate_from_point_in_time_inputs(
        weights=[50, 50],
        market_cap=[1000, 1000],
        ttm_earnings=[100, -20],
        book_value=[500, 300],
        rolling_12m_dividends=[20, 10],
    )
    assert x['pe_publishable'] is True
    assert math.isclose(x['aggregate_earnings_yield'], 0.04, abs_tol=1e-12)
    assert math.isclose(x['pe'], 25.0, abs_tol=1e-12)
    assert math.isclose(x['pb'], 2.5, abs_tol=1e-12)
    assert math.isclose(x['dividend_yield_pct'], 1.5, abs_tol=1e-12)


def test_zero_earning_constituent_is_valid():
    x = a.aggregate_from_point_in_time_inputs(
        weights=[40, 60],
        market_cap=[1000, 1000],
        ttm_earnings=[0, 100],
        book_value=[300, 500],
        rolling_12m_dividends=[0, 20],
    )
    assert x['pe_publishable'] is True
    assert math.isclose(x['pe'], 1 / 0.06, rel_tol=1e-12)


def test_non_positive_aggregate_earnings_suppresses_pe():
    x = a.aggregate_from_point_in_time_inputs(
        weights=[50, 50],
        market_cap=[1000, 1000],
        ttm_earnings=[50, -60],
        book_value=[500, 500],
        rolling_12m_dividends=[10, 10],
    )
    assert x['pe'] is None
    assert x['pe_publishable'] is False
    assert x['pe_nonpublication_reason'] == 'aggregate_adjusted_earnings_non_positive'


def test_negative_book_value_contribution_is_not_silently_dropped():
    x = a.aggregate_from_point_in_time_inputs(
        weights=[80, 20],
        market_cap=[1000, 1000],
        ttm_earnings=[100, 20],
        book_value=[500, -100],
        rolling_12m_dividends=[10, 0],
    )
    # Aggregate book yield = .8*.5 + .2*(-.1) = .38.
    assert math.isclose(x['aggregate_book_yield'], 0.38, abs_tol=1e-12)
    assert math.isclose(x['pb'], 1 / 0.38, rel_tol=1e-12)


def _complete_rows(n=50):
    return [{
        'weight': 2.0,
        'market_cap': 1000.0,
        'ttm_earnings': 50.0,
        'book_value': 300.0,
        'rolling_12m_dividends': 10.0,
        'filing_ok': True,
        'dividend_history_ok': True,
        'market_cap_basis_ok': True,
        'corporate_action_continuity_ok': True,
    } for _ in range(n)]


def test_strict_month_gate_accepts_signed_earnings():
    rows = _complete_rows()
    rows[7]['ttm_earnings'] = -25.0
    ok, why = a.strict_month_inputs_complete(rows)
    assert ok and why == 'complete'


def test_strict_month_gate_still_fails_missing_point_in_time_evidence():
    rows = _complete_rows()
    rows[4]['filing_ok'] = False
    ok, why = a.strict_month_inputs_complete(rows)
    assert not ok and why == 'filing_not_point_in_time'


def test_strict_month_gate_requires_market_cap_basis_and_corporate_action_continuity():
    rows = _complete_rows()
    rows[1]['market_cap_basis_ok'] = False
    ok, why = a.strict_month_inputs_complete(rows)
    assert not ok and why == 'market_cap_basis_inconsistent'
    rows = _complete_rows()
    rows[2]['corporate_action_continuity_ok'] = False
    ok, why = a.strict_month_inputs_complete(rows)
    assert not ok and why == 'corporate_action_continuity_incomplete'
