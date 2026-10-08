"""Static regression checks for research-output publication ownership.

A research refresh must never publish the multi-asset packet: the dedicated
multi-asset workflow owns that snapshot-coupled file. Research-generated
files must be ignored by the core refresh push trigger to avoid loops.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ResearchPublisherOwnershipTests(unittest.TestCase):
    def test_single_multiasset_publisher(self):
        optional = (ROOT / ".github/workflows/research-refresh.yml").read_text()
        dedicated = (ROOT / ".github/workflows/multiasset-refresh.yml").read_text()
        publish = optional.split("Publish successful research outputs independently of live data", 1)[1]
        self.assertNotIn("data/multiasset.json", publish)
        self.assertIn("git add data/multiasset.json", dedicated)

    def test_optional_publication_cannot_retrigger_core(self):
        optional = (ROOT / ".github/workflows/research-refresh.yml").read_text()
        core = (ROOT / ".github/workflows/refresh-data.yml").read_text()
        match = re.search(r"paths=\(([^)]*)\)", optional)
        self.assertIsNotNone(match)
        outputs = set(match.group(1).split())
        ignored_section = core.split("paths-ignore:", 1)[1].split("schedule:", 1)[0]
        ignored = set(re.findall(r'^\s*-\s*["\']([^"\']+)["\']', ignored_section, re.M))
        self.assertFalse(outputs - ignored, f"Optional outputs trigger core refresh: {outputs - ignored}")

    def test_optional_research_refuses_stale_core(self):
        optional = (ROOT / ".github/workflows/research-refresh.yml").read_text()
        self.assertIn("source_core_sha=$(git hash-object data/latest.json)", optional)
        self.assertIn("remote_core_sha=$(git rev-parse origin/main:data/latest.json)", optional)
        self.assertIn('if [[ "$source_core_sha" != "$remote_core_sha" ]]', optional)


if __name__ == "__main__":
    unittest.main()
