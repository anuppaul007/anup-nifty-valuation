"""Numerical reproduction must fail closed; synthetic values only."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from calibration_anchor_guard import enforce_reproduction, verify_publication


class ReproductionTests(unittest.TestCase):
    def test_valid_reproduction(self):
        with tempfile.TemporaryDirectory() as d:
            enforce_reproduction(Path(d) / 'audit.json', 'synthetic-v', 43.0, 43.0)

    def test_mismatch_and_nonfinite_production(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'audit.json'
            for actual, expected, reason in [
                (45.0, 43.0, 'production_reproduction_mismatch'),
                (float('nan'), 43.0, 'invalid_production_equity'),
                (101.0, 43.0, 'invalid_production_equity')
            ]:
                with self.subTest(reason=reason):
                    with self.assertRaises(RuntimeError):
                        enforce_reproduction(output, 'synthetic-v', actual, expected)
                    report = json.loads(output.read_text())
                    self.assertEqual(report['publication_status'], 'withheld')
                    self.assertEqual(report['withheld_reason'], reason)
                    with self.assertRaises(SystemExit):
                        verify_publication(output)


if __name__ == '__main__':
    unittest.main()
