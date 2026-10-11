"""Regression tests for absent reliability comparison (stdlib only)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "calibration_stability_audit.py"


def test_missing_anchor_guard_present():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "isinstance(comparison,dict)" in source
    assert "expected_value is None" in source
    assert "math.isfinite(expected)" in source
    assert "reliability['current_formula_comparison']" not in source


def test_script_compiles():
    import ast
    ast.parse(SCRIPT.read_text(encoding="utf-8"))
