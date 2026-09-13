# Fair Null, Placebo, and Macro Crash-Guard Research

## Status

**Research branch only. No live allocation change.**

This work addresses three high-priority robustness criticisms without violating the project's no-auto-promotion rule.

## 1. Beta-matched static benchmark

The fair null is a constant equity target equal to the dynamic valuation rule's realised mean target weight over the aligned sample. It uses the same equity/debt return series, drift-aware monthly rebalancing, and 10 bp one-way turnover-cost convention.

The audit also publishes a Brinson-style allocation/timing term:

`(w_t - w_bar) * (R_equity_t - R_debt_t)`

and reports the net dynamic-minus-static monthly timing series with a descriptive t-stat. The t-stat is not treated as independent-month statistical proof because serial dependence reduces effective sample size.

Run:

```bash
python scripts/fair_null_placebo_audit.py
```

Output:

`data/fair_null_placebo_audit.json`

## 2. Random-weight placebo

Instead of inventing a synthetic AR process and merely approximating the real rule's path properties, the audit uses **circular shifts of the actual weight path**.

A circular shift preserves exactly:

- the mean equity weight,
- the empirical weight distribution,
- circular total target-weight turnover,
- circular lag-1 autocorrelation.

It destroys only the calendar alignment between weights and future returns. That makes it a direct placebo for the claim that *timing* adds value.

Every non-zero unique shift is evaluated. A 1,000-draw seeded Monte Carlo sample of those shifts is also reported for compatibility with the requested placebo count, but the exact percentile across all unique shifts is the preferred result and the report discloses the number of unique paths.

Realised trading turnover after market drift is allowed to differ across shifts because that interaction is part of path alignment, not a property of the raw weight signal.

## 3. Macro authority at valuation extremes

The current live rule uses symmetric extreme-valuation damping. At a very cheap endpoint, the damping can fall to zero, so even severe negative macro conditions can lose all authority.

The external criticism correctly identifies that as a crash-resistance weakness. However, the suggested wording to "damp macro toward zero at the cheap endpoint" would preserve the same defect rather than fix it.

The research candidate therefore uses the logically opposite asymmetric rule:

- **Cheap side (`z < 0`)**: keep full macro authority.
- **Expensive side (`z >= 0`)**: retain the current valuation damping.

With the existing `macroMax = 6`, a hypothetical 100% valuation-core equity signal and maximum negative macro score becomes a 94% candidate equity signal instead of remaining at 100%.

This is intentionally modest. It removes the logical zero-authority defect without pretending that a 6 pp macro overlay alone is a complete crash-control system. The separately governed trend challenger remains the stronger price-regime crash-defense candidate.

Implementation:

`macro_guard_candidate.js`

Test:

```bash
node tests/macro_guard_candidate.test.cjs
```

## Governance

Neither a favorable beta-matched comparison, a high placebo percentile, nor the macro-guard candidate can change `model.js` automatically. Any live change requires a separate decision after reviewing the evidence, costs, taxes, data vintage limitations, and prospective record.
