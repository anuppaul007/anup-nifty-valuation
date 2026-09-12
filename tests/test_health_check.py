import sys,unittest
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from health_check import packet_check
class HealthTests(unittest.TestCase):
 def test_exact_72_hour_gate(self):
  now=datetime(2026,9,12,tzinfo=timezone.utc)
  self.assertTrue(packet_check({'schema_version':4,'generated_at':'2026-09-09T00:00:00Z'},now)[0])
  self.assertFalse(packet_check({'schema_version':4,'generated_at':'2026-09-08T23:59:59Z'},now)[0])
 def test_old_schema_and_invalid_or_future_time(self):
  now=datetime(2026,9,12,tzinfo=timezone.utc)
  for p in [{'schema_version':3},{'schema_version':4,'generated_at':'bad'},{'schema_version':4,'generated_at':'2026-09-13T00:00:00Z'}]:self.assertFalse(packet_check(p,now)[0])
