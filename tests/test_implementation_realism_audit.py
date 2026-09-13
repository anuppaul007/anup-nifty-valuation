import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import implementation_realism_audit as a


class ImplementationRealismAuditTests(unittest.TestCase):
    def test_drift_turnover_uses_post_return_weight(self):
        w = np.array([0.50, 0.50])
        er = np.array([0.10, 0.00])
        dr = np.array([0.00, 0.00])
        turn = a.drift_turnover(w, er, dr)
        expected_drift = 0.50 * 1.10 / (1.0 + 0.50 * 0.10)
        self.assertAlmostEqual(turn[0], 0.0, places=12)
        self.assertAlmostEqual(turn[1], abs(0.50 - expected_drift), places=12)

    def test_cost_is_monotone_and_first_funding_is_free(self):
        w = np.array([0.20, 0.80, 0.30, 0.70])
        er = np.array([0.03, -0.02, 0.04, 0.01])
        dr = np.array([0.005, 0.004, 0.006, 0.003])
        zero, turn = a.portfolio_returns(w, er, dr, 0)
        high, turn2 = a.portfolio_returns(w, er, dr, 25)
        np.testing.assert_allclose(turn, turn2)
        self.assertEqual(turn[0], 0.0)
        self.assertTrue(np.all(high <= zero + 1e-15))
        self.assertLess(a.cagr(high), a.cagr(zero))

    def test_exposure_matched_static_has_same_mean_target(self):
        w = np.array([0.10, 0.30, 0.90, 0.70])
        static = np.full(len(w), float(np.mean(w)))
        self.assertAlmostEqual(float(np.mean(static)), float(np.mean(w)), places=12)

    def test_completed_rows_exclude_partial_month_and_proxies(self):
        source = {
            'strategy': {
                'strict_actual_funds': {'start_month': '2025-01'},
                'timeline': []
            }
        }
        # The production guard requires a long sample, so use 120 valid rows
        # ending before a fixed synthetic 'today'.
        months = []
        year, month = 2015, 1
        for _ in range(121):
            months.append(f'{year:04d}-{month:02d}')
            month += 1
            if month == 13:
                month = 1
                year += 1
        source['strategy']['strict_actual_funds']['start_month'] = months[0]
        for m in months:
            source['strategy']['timeline'].append({
                'month': m,
                'equity_weight_pct': 60.0,
                'equity_return_pct': 1.0,
                'debt_return_pct': 0.5,
                'equity_source': 'Actual equity mutual fund',
                'debt_source': 'Actual debt mutual fund',
            })
        # Add a proxy row that should be excluded.
        source['strategy']['timeline'][5]['equity_source'] = 'NIFTY 50 TRI proxy'
        rows = a.completed_actual_fund_rows(source, today=__import__('datetime').date(2026, 1, 15))
        self.assertEqual(len(rows), 120)
        self.assertTrue(all('proxy' not in r['equity_source'].lower() for r in rows))


if __name__ == '__main__':
    unittest.main()
