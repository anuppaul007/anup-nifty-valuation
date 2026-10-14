# Calibration anchor review handoff (2026-10-14)

Status: draft, awaiting independent review. V3.13 production unchanged. Research-only.

Objective: withhold calibration sensitivity publication when the reliability anchor is missing, null, invalid, nonfinite, outside 0–100, or mismatched against the independently reproduced policy percentage.

Inputs: local reliability and latest-data JSON. No return series or sealed holdout targets accessed. Changed files: calibration anchor helper, calibration audit, three regression tests, and audit workflow.

Reproduce: `python -m unittest discover -s tests -p 'test_calibration_*.py' -v`; `python scripts/calibration_stability_audit.py`; `python scripts/calibration_stability_audit.py --verify-publication`.

Developer CI evidence: run 38500802955 completed successfully on 2026-10-14; six executable tests passed, audit and explicit publication gate passed, research artifact uploaded.

Strongest counter-evidence: no complete synthetic entrypoint test for the missing-anchor branch yet; schema v2 consumer compatibility not independently checked. A deliberately withheld report causes a red publication gate.

Reviewer questions: validate full entrypoint failure paths, consumer compatibility, mismatch tolerance, strict numeric input contract, and artifact-on-failure semantics. Acceptance requires independent review plus current-head CI success before merge.

Next milestone: finish PR #50 independent review; then six-month numerical reconstruction. No live allocation changes.
