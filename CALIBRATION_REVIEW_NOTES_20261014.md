# Calibration anchor review handoff (2026-10-14)

Status: draft, awaiting independent review. V3.13 production unchanged. Research-only.

Objective: withhold calibration sensitivity publication when the reliability anchor is missing, null, invalid, nonfinite, outside 0–100, or mismatched against the independently reproduced policy percentage.

Inputs: local reliability and latest-data JSON. No return series or sealed holdout targets accessed. Changed files: calibration anchor helper, calibration audit, three regression tests, and audit workflow.

Reproduce: `python -m unittest discover -s tests -p 'test_calibration_*.py' -v`; `python scripts/calibration_stability_audit.py`; `python scripts/calibration_stability_audit.py --verify-publication`.

Developer CI evidence: run 38500969533 completed successfully on 2026-10-14; seven executable tests passed, audit and explicit publication gate passed, research artifact uploaded.

Strongest counter-evidence: one synthetic missing-comparison entrypoint test passes, but null/nonfinite/mismatch entrypoint paths and schema v2 consumer compatibility are not independently checked. A deliberately withheld report causes a red publication gate; this is intentional, but needs independent release-risk review.

Reviewer questions: validate full entrypoint failure paths, consumer compatibility, mismatch tolerance, strict numeric input contract, and artifact-on-failure semantics. Acceptance requires independent review plus current-head CI success before merge.

Next milestone: finish PR #50 independent review; then six-month numerical reconstruction. No live allocation changes.


## Review handoff update — 2026-10-23 (research-only; NOT independently validated)

- **Affected version / baseline:** V3.13 production policy unchanged; draft PR #50 head `bec59dfec3941c21d7ee2a1c7e1421985081f0ab` at preparation, main was `ee57c131b752c4c90e2a00e62e82ed20df412fda`. Recheck both before review.
- **Source / vintage:** The descriptive 36-month screen is `data/monthly_signal_screen.json`, generated 2026-09-12T03:33:10.958501+00:00, with its own explicit caveat that historical yield publication times/vintages are NOT verified. Live reliability anchor derives from `data/latest.json` and the separately hashed 10-source reliability receipt. New screen SHA256 binds *bytes*, not PIT correctness.
- **Objective / hypothesis:** An attacker or accidental publisher could reuse a previously green schema-2 sensitivity artifact after screen bytes change while the reliability numeric equity anchor stays equal. The publication gate must reject that replay without changing allocation logic.
- **Changed files:** `scripts/calibration_anchor_guard.py` (screen SHA256 and required gate context), `scripts/calibration_stability_audit.py` (emit and verify screen digest), `tests/test_calibration_screen_receipt.py` (synthetic real entrypoint, mutation/replay, missing/null/bool/string/NaN/infinite/out-of-range/mismatch, stale hash/vintage and missing screen), `.github/workflows/calibration-stability-audit.yml` (test path trigger). Previous PR #50 provenance and anchor checks remain in place.
- **Reproduction commands:** `python -m unittest discover -s tests -p 'test_calibration_*.py' -v`; `python scripts/calibration_stability_audit.py`; `python scripts/calibration_stability_audit.py --verify-publication`. For synthetic negative cases, use the unittest command; no historical returns or sealed holdout inputs are used.
- **CI / merge evidence:** The earlier 14-test CI run 39713623262 passed on previous head e48f86b8, **not** on these new commits. Current-head CI remains UNVERIFIED until its exact commit/job results are inspected. No independent human review, no merge, no release authorization.
- **Contradictory evidence:** The screen is descriptive research, not a live allocation input; earlier main operational health was green and no stale replay exploit has been observed. A byte digest alone cannot certify source publication vintage, XBRL accounting integrity, or downstream schema-2 compatibility. Regenerating an artifact against a newly modified screen will produce a new digest; this is lineage, not a data-truth proof.
- **Residual risks / reviewer questions:** Does the optional-research artifact require its own immutable screen vintage registry? Do any downstream consumers accept schema 1 or ignore `publication_status`? Does a withheld result stop optional publishing without incorrectly blocking healthy core allocation? Can a replay occur between audit and upload? Is the public branch/release protected by independently enforced checks? Is the branch's large divergence from main safely reconciled?
- **Acceptance criteria:** Actual current-head CI all green; executable synthetic replay and negative entrypoint checks; explicit downstream consumer/release contract; independently submitted human review and documented dissent; branch reconciliation and enforceable release-risk controls. Remain draft/unmerged until all pass. Production V3.13, sealed 30-month holdout and live allocation are out of scope.
