"""End-to-end synthetic missing-anchor regression; no historical target data."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import calibration_stability_audit as a


class WithheldEntrypointTest(unittest.TestCase):
    def test_missing_anchor_writes_withheld_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            screen, latest, reliability, output = [p / x for x in ('screen.json', 'latest.json', 'reliability.json', 'out.json')]
            rows = [{'signal_date': str(i), 'methodology_era': 'Current ratio definitions',
                     'pe': 20 + i*.1, 'pb': 3 + i*.03,
                     'dy': 1 + i*.02, 'gsec10': 6 + i*.04} for i in range(36)]
            screen.write_text(json.dumps({'records': rows}))
            latest.write_text(json.dumps({
                'model_version': a.guard_model_source(), 'generated_at': 'synthetic',
                'nifty': {'date': 'synthetic', 'level': 20000, 'pe': 22,
                          'pb': 3.5, 'div_yield': 1.25, 'gsec10': 6.5},
                'earnings': {'score': 0}, 'trend': {'risk_off': False}
            }))
            reliability.write_text('{}')
            with patch.object(a, 'SCREEN', screen), patch.object(a, 'LATEST', latest), patch.object(a, 'RELIABILITY', reliability), patch.object(a, 'OUT', output):
                a.main()
            report = json.loads(output.read_text())
            self.assertEqual(report['publication_status'], 'withheld')
            self.assertEqual(report['withheld_reason'], 'missing_comparison')
            self.assertEqual(report['variants'], [])
            reliability.write_text(json.dumps({
                'current_formula_comparison': {'new_policy_equity_pct': 50.0}
            }))
            with patch.object(a, 'SCREEN', screen), patch.object(a, 'LATEST', latest), \
                 patch.object(a, 'RELIABILITY', reliability), patch.object(a, 'OUT', output), \
                 patch.object(a, 'validate_provenance', return_value='stale_source_hash') as check:
                a.main()
                check.assert_called_once()
            report = json.loads(output.read_text())
            self.assertEqual(report['publication_status'], 'withheld')
            self.assertEqual(report['withheld_reason'], 'stale_source_hash')


if __name__ == '__main__':
    unittest.main()
