"""Executable synthetic-only withholding and publication gate regressions."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from calibration_anchor_guard import write_withheld, verify_publication


class PublicationGateTests(unittest.TestCase):
    def test_withheld_is_explicit_and_never_published(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'audit.json'
            for reason in ('missing_anchor', 'null_anchor', 'nonfinite_anchor', 'production_reproduction_mismatch'):
                with self.subTest(reason=reason):
                    write_withheld(output, reason, 'synthetic-v')
                    report = json.loads(output.read_text())
                    self.assertEqual(report['publication_status'], 'withheld')
                    self.assertEqual(report['withheld_reason'], reason)
                    self.assertIsNone(report['production_reproduction'])
                    self.assertEqual(report['variants'], [])
                    with self.assertRaisesRegex(SystemExit, 'calibration_publication_blocked'):
                        verify_publication(output)

    def test_missing_corrupt_or_incomplete_output_fails(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'audit.json'
            with self.assertRaisesRegex(SystemExit, 'artifact missing'):
                verify_publication(output)
            output.write_text('not-json')
            with self.assertRaisesRegex(SystemExit, 'artifact unreadable'):
                verify_publication(output)
            output.write_text('{"publication_status":"published"}')
            with self.assertRaisesRegex(SystemExit, 'incomplete or unsafe'):
                verify_publication(output)


if __name__ == '__main__':
    unittest.main()
