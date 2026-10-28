"""Synthetic provenance regression tests. No holdout or financial records."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import calibration_anchor_guard as guard


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.paths = ('model.js', 'data/latest.json', 'policy.json')
        for relative in self.paths:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('synthetic:' + relative, encoding='utf-8')
        self.latest = {'model_version': 'synthetic-v',
                       'generated_at': '2026-10-15T17:49:16+00:00'}
        self.doc = {
            'schema_version': 1,
            'status': 'structural_checks_passed',
            'allocation_ready_at_capture': True,
            'hold_reason': None,
            'model_version': 'synthetic-v',
            'evaluated_at': self.latest['generated_at'],
            'source_hashes': {
                p: hashlib.sha256((self.root / p).read_bytes()).hexdigest()
                for p in self.paths
            },
            'current_formula_comparison': {'new_policy_equity_pct': 40.0},
        }
        patcher = patch.object(guard, 'RELIABILITY_SOURCE_PATHS', self.paths)
        patcher.start()
        self.addCleanup(patcher.stop)

    def check(self, doc=None, latest=None):
        return guard.validate_provenance(
            self.doc if doc is None else doc, root=self.root,
            latest=self.latest if latest is None else latest,
            model_version='synthetic-v')

    def test_exact_vintage_and_hashes_pass(self):
        self.assertIsNone(self.check())

    def test_stale_packet_timestamp_is_rejected_even_when_equity_matches(self):
        latest = dict(self.latest, generated_at='2026-10-15T18:00:00+00:00')
        self.assertEqual(self.check(latest=latest), 'stale_reliability_vintage')

    def test_source_byte_change_is_rejected_even_when_equity_matches(self):
        (self.root / 'policy.json').write_text('changed synthetic policy')
        self.assertEqual(self.check(), 'stale_source_hash')

    def test_missing_extra_and_malformed_hashes_fail_closed(self):
        for mutation, reason in (
            (lambda d: d['source_hashes'].pop('model.js'), 'missing_or_extra_source_hash'),
            (lambda d: d['source_hashes'].update({'extra.txt': 'a' * 64}), 'missing_or_extra_source_hash'),
            (lambda d: d['source_hashes'].update({'model.js': 'garbage'}), 'invalid_source_hash'),
        ):
            with self.subTest(reason=reason):
                doc = json.loads(json.dumps(self.doc))
                mutation(doc)
                self.assertEqual(self.check(doc=doc), reason)

    def test_status_version_readiness_and_hold_fail_closed(self):
        for key, value, reason in (
            ('status', 'withheld', 'unverified_reliability_status'),
            ('allocation_ready_at_capture', False, 'allocation_not_ready_at_capture'),
            ('hold_reason', 'missing_yield', 'reliability_hold_reason'),
            ('model_version', 'other-v', 'model_version_mismatch'),
            ('schema_version', 2, 'invalid_reliability_schema'),
        ):
            with self.subTest(key=key):
                doc = json.loads(json.dumps(self.doc))
                doc[key] = value
                self.assertEqual(self.check(doc=doc), reason)

    def test_naive_or_invalid_timestamp_is_rejected(self):
        for stamp in ('2026-10-15T17:49:16', 'not-a-date'):
            with self.subTest(stamp=stamp):
                doc = dict(self.doc, evaluated_at=stamp)
                latest = dict(self.latest, generated_at=stamp)
                self.assertEqual(self.check(doc=doc, latest=latest), 'invalid_evaluation_timestamp')

    def test_missing_source_file_fails_closed(self):
        (self.root / 'policy.json').unlink()
        self.assertEqual(self.check(), 'unavailable_source_file')


if __name__ == '__main__':
    unittest.main()
