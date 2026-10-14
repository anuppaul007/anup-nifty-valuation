"""Synthetic-only executable regression tests for reliability-anchor validation."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from calibration_anchor_guard import validate_anchor


class ReliabilityAnchorTests(unittest.TestCase):
    def test_missing_invalid_and_nonfinite(self):
        cases = [
            ({}, 'missing_comparison'),
            ({'current_formula_comparison': None}, 'missing_comparison'),
            ({'current_formula_comparison': []}, 'missing_comparison'),
            ({'current_formula_comparison': {}}, 'missing_anchor'),
            ({'current_formula_comparison': {'new_policy_equity_pct': None}}, 'null_anchor'),
            ({'current_formula_comparison': {'new_policy_equity_pct': True}}, 'invalid_anchor_type'),
            ({'current_formula_comparison': {'new_policy_equity_pct': '45'}}, 'invalid_anchor_type'),
            ({'current_formula_comparison': {'new_policy_equity_pct': 'bad'}}, 'invalid_anchor_type'),
            ({'current_formula_comparison': {'new_policy_equity_pct': math.nan}}, 'nonfinite_anchor'),
            ({'current_formula_comparison': {'new_policy_equity_pct': math.inf}}, 'nonfinite_anchor'),
            ({'current_formula_comparison': {'new_policy_equity_pct': -1}}, 'out_of_range_anchor'),
            ({'current_formula_comparison': {'new_policy_equity_pct': 101}}, 'out_of_range_anchor'),
            (None, 'invalid_reliability_document'),
            ([], 'invalid_reliability_document')
        ]
        for document, reason in cases:
            with self.subTest(document=repr(document)):
                value, error = validate_anchor(document)
                self.assertIsNone(value)
                self.assertEqual(error, reason)

    def test_valid_numeric_boundaries(self):
        for number in [0, 1, 50.5, 100]:
            with self.subTest(number=number):
                self.assertEqual(validate_anchor(
                    {'current_formula_comparison': {'new_policy_equity_pct': number}}),
                    (float(number), None))


if __name__ == '__main__':
    unittest.main()
