import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import robust_evaluation as re  # noqa: E402


class RobustEvaluationTests(unittest.TestCase):
    def test_cagr_identity(self):
        self.assertAlmostEqual(re.cagr(np.zeros(12)), 0.0, places=12)

    def test_effective_sample_not_above_raw(self):
        x = np.linspace(0, 1, 60)
        q = re.effective_sample_size(x)
        self.assertLessEqual(q["effective_n"], q["raw_n"])
        self.assertGreaterEqual(q["effective_n"], 1)

    def test_block_bootstrap_preserves_positive_constant_edge(self):
        q = re.moving_block_bootstrap(np.full(36, 0.001), block=6, draws=200, seed=7)
        self.assertIsNotNone(q)
        self.assertGreater(q["ci95_pp"][0], 0)
        self.assertAlmostEqual(q["annualized_mean_timing_pp"], 1.2, places=9)

    def test_deflated_sharpe_probability_is_bounded(self):
        x = np.array([0.01, 0.02, -0.005, 0.015, 0.01, -0.002] * 8, dtype=float)
        q = re.deflated_sharpe_probability(x, benchmark_sr=0.05)
        self.assertIsNotNone(q)
        self.assertGreaterEqual(q["probability"], 0)
        self.assertLessEqual(q["probability"], 1)
        self.assertEqual(q["moment_source"], "selected exposure-matched timing-residual series")

    def test_ar1_fit_recovers_persistence(self):
        rng = np.random.default_rng(123)
        x = np.empty(2000)
        x[0] = 0.0
        for i in range(1, len(x)):
            x[i] = 0.8 * x[i - 1] + rng.normal(0, 0.4)
        q = re.fit_ar1(x)
        self.assertAlmostEqual(q["phi"], 0.8, delta=0.05)
        self.assertGreater(q["sd"], 0)
        self.assertGreater(q["innovation_sd"], 0)

    def test_ar1_simulation_preserves_scale_and_persistence(self):
        params = {"mean": 0.3, "sd": 1.2, "phi": 0.75, "innovation_sd": 1.2 * math.sqrt(1 - 0.75**2)}
        x = re.simulate_ar1(params, 10000, np.random.default_rng(7), burn=500)
        self.assertAlmostEqual(float(np.mean(x)), 0.3, delta=0.08)
        self.assertAlmostEqual(float(np.std(x, ddof=1)), 1.2, delta=0.08)
        self.assertAlmostEqual(re.acf(x, 1), 0.75, delta=0.04)

    def test_fair_pe_fan(self):
        d = {
            "model_version": "3.10-pb-regime-1",
            "nifty": {"pe": 20.0, "pb": 3.0, "div_yield": 1.2, "gsec10": 7.0},
            "earnings": {"score": 0.0},
            "macro": {"score": 0.0},
        }
        q = re.fair_pe_fan(d)
        self.assertEqual(q["status"], "complete")
        self.assertEqual(len(q["fan"]), 9)
        self.assertGreater(q["spread_pp"], 0)
        for row in q["fan"]:
            self.assertTrue(math.isfinite(row["mechanical_full_equity_pct"]))
            self.assertGreaterEqual(row["mechanical_full_equity_pct"], 0)
            self.assertLessEqual(row["mechanical_full_equity_pct"], 100)

    def test_track_record_inflates_with_positive_autocorrelation(self):
        a = re.track_record_heuristic(0.0)
        b = re.track_record_heuristic(0.8)
        self.assertGreater(b["approx_calendar_months_95pct"], a["approx_calendar_months_95pct"])


if __name__ == "__main__":
    unittest.main()
