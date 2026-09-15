# Institutional Readiness Score v1

**Status:** governance / evidence dashboard only. **Zero live allocation authority.**

This score is a readiness index, not a probability that the model is correct and not an investment-performance forecast. It exists to prevent strong engineering or documentation from being mistaken for demonstrated investment efficacy.

## CIO admission rule

The model is eligible for consideration in the CIO framework only when all three conditions hold simultaneously:

1. weighted Institutional Readiness Score >= **90/100**;
2. every critical dimension >= **80/100**; and
3. every controlling pre-registered promotion gate is passed, with no unresolved material model-risk defect.

A high weighted average cannot compensate for a failed critical dimension or failed promotion gate.

## Frozen v1 weights and current assessment — 14 Sep 2026

| Dimension | Weight | Critical | Score | Weighted points | Evidence-based reason |
|---|---:|:---:|---:|---:|---|
| Data integrity / point-in-time lineage | 20% | Yes | 58 | 11.60 | Development source routing is strong but only 294/300 company-months are machine-reproducible; the six Nestle rows use a controlled evidence bridge and full independent P/E, P/B and dividend-yield reconstruction is not yet complete. Holdout remains sealed. |
| Reproducibility / operational reliability | 15% | Yes | 88 | 13.20 | Automated refresh, stale/mismatch fail-closed behavior, publication monitoring, synchronized multi-asset refresh, CI guards and reproducibility artifacts are substantial. This is below 90 because operational history is still short and recent defects required repair. |
| Economic rationale / specification discipline | 10% | No | 78 | 7.80 | Valuation, earnings, macro and trend components have explicit economic rationales and governance; however, lens redundancy is material and some reference choices remain influential. |
| Historical efficacy after exposure matching, costs and taxes | 20% | Yes | 30 | 6.00 | Current robust evaluation is NOT_ELIGIBLE_FOR_PROMOTION. Exposure-matched excess CAGR is only +0.16 pp; placebo 95th-percentile and paired block-bootstrap gates fail; taxable after-tax implementation remains unresolved. |
| Statistical robustness / multiple-testing control | 15% | Yes | 42 | 6.30 | Trial registry, placebo, bootstrap, DSR and PBO controls exist. DSR passes, but PBO fails and bootstrap intervals include zero; effective timing sample is small and serial dependence is high. |
| Drawdown / insurance characterization | 7.5% | No | 68 | 5.10 | SMA10 insurance cost and episode behavior are explicitly measured, but the challenger fails its historical promotion gate and is not demonstrated alpha. |
| Independent replication / adversarial review | 7.5% | Yes | 20 | 1.50 | External review packet and manifest process exist, but the model is explicitly not independently validated and no qualifying external replication is recorded. |
| Prospective live evidence | 5% | Yes | 5 | 0.25 | Robust evaluation records 1 completed monthly decision versus a minimum 60 before promotion review. |
| **Total** | **100%** |  |  | **51.75 / 100** | **Not CIO eligible.** |

Current Institutional Readiness Score: **51.8 / 100** (rounded to one decimal).

## Controlling gate state

The current robust-evaluation decision is **NOT_ELIGIBLE_FOR_PROMOTION**. Failed or unresolved controlling gates include:

- placebo 95th-percentile gate;
- paired moving-block bootstrap lower-bound gate;
- CSCV/PBO gate;
- prospective evidence minimum;
- certified point-in-time full-stack history;
- taxable after-tax implementation test.

The positive exposure-matched timing edge and favorable Deflated Sharpe diagnostic do not override those failures.

## Scoring discipline

Scores may change only when repository evidence changes. A score change must cite the new artifact, test, independent review, or completed prospective observation that justifies it. Scores must not be raised because the model 'feels' more mature.

For critical dimensions, 80 means the dimension is strong enough for institutional use subject to the other gates; 90 means strong evidence with only minor residual limitations. Scores below 50 indicate material evidence gaps. A score of zero is appropriate when no relevant evidence exists.

Weights and thresholds are frozen in this v1 document before the score can influence any CIO admission decision. Changing weights or thresholds later requires a separately documented governance revision and must not be motivated by making the current model pass.

## Machine enforcement

The frozen v1 weights, critical flags, assessment scores and CIO thresholds are mirrored in `institutional_readiness_policy_v1.json`. `scripts/institutional_readiness.py` mechanically recomputes the weighted score from that frozen policy and reads the controlling gate matrix from `data/robust_evaluation_summary.json`; it does not infer, optimize or tune assessment scores.

`data/institutional_readiness.json` is the deterministic machine-readable status. CI fails if that status drifts from the policy/evidence inputs, if a required promotion gate is missing or is not an explicit boolean, if weights stop summing exactly to 100, if admission thresholds are weakened, or if a score attempts to bypass a failed critical dimension, failed promotion gate, or uncleared material model-risk defect.

The readiness document, frozen policy, evaluator and generated status are all required inputs to the immutable external-review manifest, so a reviewer can identify exactly which readiness rules and status were reviewed. This strengthens governance/reproducibility only: **the score remains 51.8/100, V3.13 remains unchanged, the holdout remains sealed, challengers retain zero additional authority, and live investment authority did not change.**

## Evidence anchors

- `data/robust_evaluation_summary.json`
- `data/calibration_stability_audit.json`
- `data/benchmark_audit.json`
- `data/sma10_insurance_audit.json`
- `data/sma10_episode_audit.json`
- `data/macro_authority_audit.json`
- `DEVELOPMENT_RESIDUAL_SOURCE_RESOLUTION.md`
- `EXTERNAL_REVIEW_PACKET.md`
- `validation_policy.json`
- `research_trial_registry.json`

## Current decision

**NOT CIO ELIGIBLE.** V3.13 remains useful as a research/reference signal under its existing authority, but the present evidence does not justify using the Institutional Readiness Score as a route around failed efficacy, independent-validation, point-in-time, after-tax or prospective gates.
