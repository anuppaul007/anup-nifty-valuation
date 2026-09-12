# Independent robustness audit — 12 September 2026

**The evidence does not support “no issues,” maximum returns, or treating 81% equity as a validated recommendation.** V3.7 corrects implementation defects and makes model uncertainty visible. It preserves the existing V3.6 economic weights and allocation parameters rather than selecting a new portfolio after looking at historical outcomes.

## What the backtest actually establishes

The existing study uses April 2021–July 2026 data and 63 next-month returns. It tests the valuation core, **without the earnings or macro overlays**. Current fixed reference constants were not demonstrably frozen in April 2021. Monthly OECD yields are current-vintage data, with no historical publication timestamps. Consequently, next-month signal shifting alone does not establish a point-in-time, out-of-sample macro strategy test.

The prospective ledger currently contains one signal month and zero realized 6- or 12-month outcomes. Its future overlapping 12-month observations will not be independent samples. Its numerical review gate is a governance rule, not statistical proof, and does not automatically change the live allocation.

## Defects corrected

| Issue | Correction |
|---|---|
| Drawdown started after the first return, ignoring a loss from the initial investment | Include starting wealth of 1 before accumulating returns |
| Turnover compared consecutive target percentages, ignoring market drift | Calculate the previous portfolio's post-return equity weight, then charge rebalancing costs before the following return |
| Fixed balanced benchmarks appeared free of rebalancing costs | New independent comparisons apply the same drift-aware cost assumption to fixed and dynamic portfolios |
| Missing calendar months could become one purported monthly return | Reject non-contiguous panels rather than misannualize returns |
| Wider-endpoint prospective candidates still used the original endpoint's overlay damping | Recompute damping separately for each candidate endpoint |
| Prospective snapshots checked scores and coverage but not the live engine's date gates | Invoke the same allocation engine used by the website before admitting a snapshot |
| A freshly generated packet could carry stale factors labelled live, or an inconsistent aggregate score | Revalidate every required observation date and component score, and reconstruct the aggregate, in the browser and ledger |
| A late refresh could rewrite an already closed month's ledger entry | Replace snapshots only within the current calendar month |
| Multi-series SDMX responses could silently collapse to one observation per date | Reject duplicate periods as an ambiguous source response |
| A precise headline allocation suggested more evidence than exists | Label it a research signal and show assumption ranges, severe macro scenarios and five-year earnings/valuation scenarios |

The full refresh continues to isolate source failures. Monthly data retain their observation dates; daily refresh does not pretend CPI, IIP or REER are daily observations. No missing factor is assigned a neutral score to satisfy the complete-input gate.

## Corrected historical results

Computed from the repository's saved source panel, with 10 bps per 100% one-way turnover. Initial acquisition costs and taxes are excluded. Drawdown is measured at month ends; intramonth losses can be larger. Debt is the NIFTY 10 Year Benchmark G-Sec index, which has material duration risk.

| Same full 63-month return window | CAGR | Monthly-sampled max drawdown | Calmar |
|---|---:|---:|---:|
| Fixed-reference valuation core | 8.92% | -9.60% | 0.929 |
| Monthly rebalanced 60/40 | 9.17% | -9.45% | 0.970 |
| Monthly rebalanced 70/30 | 9.79% | -10.77% | 0.909 |
| 100% NIFTY total-return index | 11.58% | -14.68% | 0.789 |

The corrections are small in this particular sample, but the original claim of superior allocation is still unsupported. The initial-drawdown defect does not imply that this particular sample's maximum drawdown changed materially.

## New calibration and publication-lag sensitivity

New research alternatives use medians and median absolute deviations from earlier months only. They give equal weights to P/E, P/B, dividend yield and earnings-yield spread, without the original implied-profitability correction. This is a combined calibration-and-weighting sensitivity, not a clean test of calibration alone. It remains a correlated lens set and is not a replacement fair-value model.

Monthly bond yields are lagged two calendar months in these alternatives as a publication-lag sensitivity. This is **not** proof that those current-vintage values were available historically. The rolling window is 36 months; the expanding alternative uses all preceding observations. Both need a warm-up and are compared on the same 27 returns, May 2024–July 2026.

| Same 27-month return window | CAGR | Monthly-sampled max drawdown |
|---|---:|---:|
| Original fixed references | 7.84% | -9.60% |
| Original references, yield lagged two months | 7.65% | -9.90% |
| Rolling 36-month references, equal lenses | 7.91% | -9.43% |
| Expanding references, equal lenses | 7.29% | -10.36% |
| 60/40 | 5.97% | -9.45% |

The relative result changes with the sample window. Twenty-seven returns cannot establish superiority. No historical winner is promoted to production. The full comparable sample also excludes the 2008 and March 2020 crashes.

Reproduce with `python scripts/robustness_audit.py`; machine-readable results are in `data/robustness.json`. Daily refresh recomputes these diagnostics from the refreshed retrospective panel. If that panel fails, the audit explicitly records unavailability without preventing otherwise valid live inputs from being saved.

## Why 81% persists

For the inspected 11 September NIFTY observation and 12 September publication:

- Valuation core: 82.71% equity.
- Earnings contribution: -1.02 percentage points.
- Macro contribution: -0.14 percentage points.
- Research signal: 81.55% equity.
- Changing only the tested curve assumptions gives **66.86–83.33% equity**. This is an assumption range, not a confidence interval or recommended allocation band.
- Setting every macro block to its maximum headwind, with valuation and earnings unchanged, still produces **78.21% equity**.
- Setting both macro and earnings to maximum headwinds still produces **75.76% equity**.

At this valuation the macro budget is only ±3.47 percentage points after damping. At extreme valuation endpoints it becomes zero. Thus the rule does not behave like a macro risk-control strategy, even though macro arithmetic is present and correct. It can recommend 100% equity in an adverse macro environment. The dashboard now states this prominently rather than implying that complete data validate the endpoints.

The aggregate is close to neutral partly because high US real yields and Brent are offset by expanding Fed assets and low REER relative to history. Those offsets are economic hypotheses, not proven causal protection. A weak rupee can improve competitiveness while raising imported inflation; high domestic nominal yields can signal either attractive carry or greater risk. Real repo rates reuse CPI, and multiple global/FX indicators are correlated. Adding more such indicators or larger weights is not automatically greater robustness.

## Coverage boundary and remaining work

The scored set includes US real yields, Fed assets, broad USD, VIX, Brent, India–US nominal yield spread, India REER, USD/INR momentum, India CPI, IIP and repo, and China manufacturing PMI/new orders. **100% coverage means these defined inputs are eligible, not that all macro conditions are covered.**

Fiscal policy, credit stress, bank liquidity, capital flows, trade balances, geopolitical events and sector-specific earnings risks do not have separate validated coefficients. Some are partly reflected in the included prices; none should be claimed as fully modeled. Unobserved shocks cannot be solved by filling a dashboard cell.

The legacy EM valuation diagnostic remains outside the scored macro model; its five historical observations are insufficient for its 12-observation calibration rule. This is not counted as a completed active factor. Its exclusion must not be mistaken for a successfully validated relative-value signal.

A defensible next production allocation design requires specifying the desired trade-off between return and drawdown, collecting timestamped releases and investable benchmarks, testing a separately designed challenger across regimes, and then evaluating genuinely forward performance. This audit does not substitute an arbitrary lower percentage for that evidence. Emergency reserves and near-term liabilities remain outside the modeled sleeve.

## Verification

36 Python tests and 10 JavaScript tests pass locally, including starting-capital drawdown, drift costs, calendar gaps, stale factors, inconsistent scores, candidate damping and immunity of earlier rolling signals to future data changes. The JavaScript suite also sweeps 190 valuation/macro combinations for bounded allocations and macro-direction monotonicity. These are implementation checks, not proof of investment performance.
