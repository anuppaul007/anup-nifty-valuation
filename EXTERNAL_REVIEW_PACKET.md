# External Review Packet — Anup Nifty Valuation

**Status:** prepared for external adversarial review; **not independently validated**.

This packet exists to make a serious outside challenge easier and harder to game. It does not turn author review, CI, AI critique, or code reproduction into independent validation.

## 1. Freeze the object being reviewed

Review an exact immutable commit SHA, never `main` or another moving branch.

Record before doing any analysis:

- commit SHA;
- review start time in UTC;
- reviewer identity or public pseudonym;
- conflicts, prior collaboration, or prior involvement with the model;
- operating system, Python/Node versions and dependency versions;
- location of the reviewer's **independent** reproduction code/files.

Run:

```bash
python scripts/build_review_manifest.py --out review_manifest.json
```

The generated manifest records the exact commit, tracked-tree cleanliness, environment information and SHA-256 digests for the model, policies, research evaluators and controlling evidence files. Preserve that manifest with the final review.

A branch name is only a convenience. The commit SHA plus hashes control the review target.

## 2. Read the adverse evidence first

Before attempting to confirm the live allocation, read the evidence that argues against strong confidence:

- `data/robust_evaluation_summary.json` — the historical timing evidence currently remains **NOT_ELIGIBLE_FOR_PROMOTION**;
- `data/calibration_stability_audit.json` — the live point estimate is materially sensitive to reasonable re-estimation in the short current-definition era;
- `data/benchmark_audit.json` — comparator choice and equity beta must be separated from residual timing value;
- `data/sma10_insurance_audit.json` and `data/sma10_episode_audit.json` — the crash brake is policy insurance with an observable premium and recovery trade-off, not validated alpha;
- `data/macro_authority_audit.json` — macro has zero live allocation authority until its decision value is demonstrated;
- `data/implementation_realism_audit.json` when present — the actual-fund reconstruction may show higher retrospective CAGR but can still show worse drawdown and is not certified point-in-time V3.13 evidence.

A reviewer must not average favorable engineering/process findings against adverse efficacy evidence.

## 3. Reproduce the current target independently

Do **not** call `model.js`, import its calculation functions, or copy/paste its implementation into the replication.

From the frozen policy definitions and the published raw live inputs, independently derive:

1. each valuation lens transformation;
2. the composite valuation score;
3. valuation-to-equity curve output;
4. earnings adjustment and eligibility gate;
5. SMA10 policy adjustment and eligibility gate;
6. macro live authority (currently zero);
7. final allocation and any withholding condition.

Report every numerical difference from the repository output, even if small. Resolve differences by evidence, not by forcing the independent code to agree.

## 4. Try to break it

The minimum falsification programme is frozen in `review_scope_v1.json`. It requires challenges to:

- point-in-time data lineage, release dates, revisions and source fallbacks;
- calibration/reference choice and the short clean-history problem;
- correlated/redundant valuation lenses;
- the historical evaluator, exposure-matched nulls and serial dependence;
- SMA10 insurance pricing and recovery/gap trade-offs;
- actual investability, turnover, fund-level costs, exit loads and tax limitations;
- deployment/cache/schema/stale-data failure modes;
- analyses that deliberately make the model look worse.

Additional comparable trials discovered during review must be logged. Do not silently discard unfavorable specifications.

## 5. Finding log

For every finding, publish at least:

| Field | Requirement |
|---|---|
| ID | Stable identifier |
| Severity | Critical / High / Medium / Low / Observation |
| Component | Data / model / evaluator / implementation / deployment / governance |
| Claim tested | Exact claim or behavior challenged |
| Reproduction | Command, code or data sufficient to reproduce |
| Expected | What the frozen specification says should happen |
| Observed | What actually happened |
| Counterexample | Smallest useful failing case, when applicable |
| Impact | Effect on allocation, evidence, or usability |
| Status | Open / Accepted / Resolved in a later version / Not reproducible |

Do not edit the reviewed commit to make findings disappear. Any fix belongs in a later version and the original finding remains part of the review record.

## 6. Required final conclusions

The review should answer these separately rather than issue one composite score:

1. **Reproducibility:** can the frozen live result be independently reproduced?
2. **Data integrity:** are the inputs and their point-in-time availability adequate for each claim actually made?
3. **Model implementation:** does the code faithfully implement the frozen policy?
4. **Statistical evidence:** what has actually been demonstrated, and what remains unproven?
5. **Implementation realism:** what portion of modeled return is investable after known costs, and what material costs remain unmodeled?
6. **Operational reliability:** does the public system fail closed on stale, malformed or mismatched evidence?
7. **Use decision:** what limited use, if any, is justified by the evidence reviewed?

Material unresolved findings must remain visible. They block a blanket claim that the model is validated or institutionally proven.

## 7. No-authority rule

An external review can increase or decrease confidence. It does **not** automatically change V3.13, promote a challenger, alter a threshold, or grant live authority to a research component. Any model change requires a separately versioned decision under the repository's governance rules.

Related governance documents:

- `INDEPENDENT_REVIEW.md`
- `review_scope_v1.json`
- `validation_policy.json`
- `research_trial_registry.json`

The objective is not to obtain a favorable review. It is to create a review process capable of producing an unfavorable result that survives publication.
