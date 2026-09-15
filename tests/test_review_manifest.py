import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_review_manifest as m


class ReviewManifestTests(unittest.TestCase):
    def test_sha256_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'x.bin'
            p.write_bytes(b'fixed review bytes\x00\x01')
            expected = hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(m.sha256_file(p), expected)

    def test_optional_missing_is_recorded_not_invented(self):
        r = m.file_record('__review_manifest_missing_optional__.json', False)
        self.assertEqual(r['path'], '__review_manifest_missing_optional__.json')
        self.assertFalse(r['required'])
        self.assertFalse(r['present'])
        self.assertNotIn('sha256', r)

    def test_required_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            m.file_record('__review_manifest_missing_required__.json', True)

    def test_required_manifest_paths_exist_in_repo(self):
        for rel in m.REQUIRED_FILES:
            with self.subTest(path=rel):
                r = m.file_record(rel, True)
                self.assertTrue(r['present'])
                self.assertTrue(r['required'])
                self.assertEqual(len(r['sha256']), 64)
                self.assertGreaterEqual(r['size_bytes'], 0)

    def test_readiness_governance_is_immutable_review_scope(self):
        required = set(m.REQUIRED_FILES)
        self.assertTrue({
            'INSTITUTIONAL_READINESS.md',
            'institutional_readiness_policy_v1.json',
            'scripts/institutional_readiness.py',
            'data/institutional_readiness.json',
            'data/robust_evaluation_summary.json',
        }.issubset(required))

    def test_requirement_parser_matches_exact_version_file(self):
        names = m.parse_requirement_names(ROOT / 'requirements.txt')
        self.assertIn('numpy', names)
        self.assertIn('pandas', names)
        self.assertIn('jugaad-data', names)
        self.assertEqual(len(names), len(set(names)))


if __name__ == '__main__':
    unittest.main()
