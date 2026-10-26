"""Synthetic downstream review-manifest contract for calibration research evidence.

No historical returns, holdout, market data, or live allocation is accessed.
This tests the actual manifest file-record consumer, not the production refresh.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_review_manifest as manifest


class CalibrationReviewManifestContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'data/calibration_stability_audit.json'
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def classify(self, value):
        self.path.write_text(json.dumps(value))
        return manifest.calibration_publication_evidence(self.path)

    @staticmethod
    def withheld():
        return {
            'schema_version': 2, 'publication_status': 'withheld',
            'withheld_reason': 'synthetic_stale_source_hash',
            'research_only': True, 'live_model_changed': False,
            'live_allocation_changed': False, 'return_data_used': False,
            'anchor_status': 'unverified', 'production_reproduction': None,
            'variants': [],
        }

    def test_legacy_nine_variant_report_is_not_certified(self):
        evidence = self.classify({'schema_version': 1, 'variants': [{}] * 9})
        self.assertEqual(evidence['classification'], 'unverified')
        self.assertEqual(evidence['reason'], 'legacy_or_unknown_schema')
        self.assertFalse(evidence['publication_gate_executed'])

    def test_published_claim_does_not_count_as_verified(self):
        evidence = self.classify({
            'schema_version': 2, 'publication_status': 'published',
            'anchor_status': 'verified', 'variants': [{}] * 9,
            'anchor_provenance': {'source_hashes': {'synthetic': 'not_real'}},
        })
        self.assertEqual(evidence['reported_publication_status'], 'published')
        self.assertEqual(evidence['classification'], 'unverified')
        self.assertEqual(evidence['reason'], 'claimed_published_not_verified_by_manifest')
        self.assertFalse(evidence['publication_gate_executed'])

    def test_explicit_safe_withheld_is_classified_without_publication_authority(self):
        evidence = self.classify(self.withheld())
        self.assertEqual(evidence['classification'], 'withheld')
        self.assertEqual(evidence['reason'], 'explicit_withheld_research_only')
        self.assertFalse(evidence['publication_gate_executed'])

    def test_malformed_withheld_cannot_appear_as_safe(self):
        for field, value in (
            ('variants', [{'policy_equity_pct': 80}]),
            ('production_reproduction', {'policy_equity_pct': 80}),
            ('anchor_status', 'verified'),
            ('withheld_reason', None),
            ('live_allocation_changed', True),
        ):
            with self.subTest(field=field):
                report = self.withheld()
                report[field] = value
                evidence = self.classify(report)
                self.assertEqual(evidence['classification'], 'unverified')
                self.assertEqual(evidence['reason'], 'malformed_withheld_artifact')

    def test_bad_json_nonfinite_and_missing_status_are_unverified(self):
        for raw in (b'{bad', b'\\xff', b'{"schema_version":2,"x":NaN}', b'[]', b'null',
                    b'{"schema_version":2}'):
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                evidence = manifest.calibration_publication_evidence(self.path)
                self.assertEqual(evidence['classification'], 'unverified')
                self.assertFalse(evidence['publication_gate_executed'])

    def test_actual_manifest_file_record_classifies_legacy_and_withheld(self):
        relative = 'data/calibration_stability_audit.json'
        with patch.object(manifest, 'ROOT', self.root):
            self.path.write_text(json.dumps({'schema_version': 1, 'variants': [{}] * 9}))
            legacy = manifest.file_record(relative, True)
            self.assertEqual(legacy['calibration_publication_evidence']['classification'], 'unverified')
            self.assertEqual(len(legacy['sha256']), 64)
            self.path.write_text(json.dumps(self.withheld()))
            withheld = manifest.file_record(relative, True)
            self.assertEqual(withheld['calibration_publication_evidence']['classification'], 'withheld')
            self.assertNotEqual(legacy['sha256'], withheld['sha256'])

    def test_other_manifest_file_records_preserve_shape(self):
        with patch.object(manifest, 'ROOT', self.root):
            p = self.root / 'other.json'
            p.write_text('{}')
            record = manifest.file_record('other.json', True)
            self.assertNotIn('calibration_publication_evidence', record)


if __name__ == '__main__':
    unittest.main()
