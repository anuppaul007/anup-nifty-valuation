# Robust Evaluation Framework

## Purpose

This framework is deliberately stricter than the allocation model. Its job is not to make the strategy look good; its job is to make weak evidence difficult to hide.

**Nothing here changes the live allocation automatically.** A failed or unavailable test remains visible. There is no weighted score that can average a critical failure into a pass.

## Evidence hierarchy

1. **Data availability first.** A full historical macro/earnings claim is not allowed unless every input was actually available before the decision. Unknown historical release time means *not testable*, not neutral-filled.
2. **Fair null before performance claims.** Dynamic allocation is compared with a static portfolio holding the same realised average equity exposure, on identical equity/debt returns and costs.
3. **Timing must beat placebo.** Every non-zero circular shift of the actual weight path is used as a placebo. This preserves the weight distribution, mean weight and serial structure while breaking calendar alignment with returns.
4. **Serial dependence is explicit.** Paired timing differences are resampled with 3-, 6- and 12-month moving blocks, and an effective sample-size diagnostic is published.
5. **Multiple testing is penalised.** The exact 24-member valuation curve family is evaluated with a Deflated Sharpe probability and CSCV probability of backtest overfitting (PBO). Other research families are counted in `research_trial_registry.json` but are not falsely pooled across incompatible samples.
6. **Calibration assumptions are exposed.** Fixed-reference, lagged-yield, rolling and expanding calibration results remain side by side.
7. **Correlated valuation lenses are measured.** The evaluator publishes the lens correlation matrix and an effective independent-lens count from the correlation eigenvalues.
8. **Reference dominance is visible.** Current allocation is recalculated mechanically while assumed fair P/E ranges from 18 to 26, with all other V3.10 inputs frozen.
9. **Crash defence remains separate.** The SMA10 challenger and the asymmetric macro crash-guard are evaluated as challengers. They do not retroactively rescue weak valuation timing evidence.
10. **Reproducibility is part of the result.** The model, source packets, policy files and evaluation inputs are SHA-256 hashed.

## Promotion gate

The research policy currently requires, at minimum:

- placebo percentile >= 95,
- Deflated Sharpe probability >= 0.95,
- CSCV PBO <= 0.10,
- the lower 95% paired moving-block bootstrap bound above zero at 3, 6 and 12 month blocks,
- at least 60 completed prospective monthly decisions,
- certified point-in-time full-stack inputs for any full-stack historical claim,
- implementation evidence matching the claim, including taxes before calling a result taxable-investor net performance.

Even if every threshold passes, promotion is **not automatic**. It only becomes eligible for a separate review.

## Current limitations that the evaluator must not hide

- The comparable valuation-core return history is short.
- The full V3.10 macro plus earnings stack does not have certified point-in-time history through the GFC and March 2020.
- Fixed valuation references applied before their freeze date contain look-ahead and are therefore sensitivity evidence only.
- Monthly return studies understate intramonth drawdowns.
- Tax-aware FIFO lot accounting is not yet implemented, so retrospective returns must not be described as after-tax taxable-investor outcomes.

## Run

```bash
python scripts/robust_evaluation.py
```

Output:

`data/robust_evaluation.json`

CI also runs the unit tests and the separate macro crash-guard candidate test.

## Interpretation

The most important output field is not a performance number. It is `decision` together with `gate_matrix`.

- `NOT_ELIGIBLE_FOR_PROMOTION` means at least one critical evidence requirement is missing or failed.
- `ELIGIBLE_FOR_SEPARATE_PROMOTION_REVIEW` would mean all declared gates passed; it still would not change the live model automatically.

This design intentionally prefers an honest `not testable` or `inconclusive` result to an impressive-looking backtest built on unverifiable assumptions.
