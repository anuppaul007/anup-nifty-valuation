import sys, unittest, tempfile, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from archive_evidence import immutable, digest, canonical, archive

class ArchiveTests(unittest.TestCase):
    def test_original_observation_timestamp_is_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'entry.json'
            immutable(p,{'first_seen_at':'2026-09-12','value':10})
            got=immutable(p,{'first_seen_at':'2026-09-13','value':10})
            self.assertEqual(got['first_seen_at'],'2026-09-12')
    def test_revised_input_cannot_overwrite_original(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'entry.json';immutable(p,{'value':10})
            with self.assertRaises(ValueError):immutable(p,{'value':11})
            self.assertEqual(json.loads(p.read_text())['value'],10)
    def test_changed_rules_get_different_version(self):
        self.assertNotEqual(digest(canonical({'macroMax':6})),digest(canonical({'macroMax':12})))
    def test_revisions_append_and_first_monthly_decision_stays_frozen(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'data').mkdir();(root/'scripts').mkdir()
            (root/'model.js').write_text('module.exports={C:{k:1.35},calculate:d=>({allocationReady:d.ready,final:d.equity})};')
            (root/'requirements.txt').write_text('')
            (root/'validation_policy.json').write_text('{}')
            p=root/'data/latest.json';p.write_text('{"ready":true,"equity":81}')
            first=archive(root,'2026-09-12T12:00:00Z')
            repeat=archive(root,'2026-09-13T12:00:00Z');self.assertEqual(repeat['snapshot_count'],1)
            p.write_text('{"ready":true,"equity":65}')
            changed=archive(root,'2026-09-14T12:00:00Z')
            self.assertEqual(changed['snapshot_count'],2);self.assertEqual(changed['decisions'][0]['equity_pct'],81)
            p.write_text('{"ready":false,"equity":null}')
            incomplete=archive(root,'2026-10-01T12:00:00Z');self.assertEqual(incomplete['decision_count'],1)

if __name__=='__main__':unittest.main()
