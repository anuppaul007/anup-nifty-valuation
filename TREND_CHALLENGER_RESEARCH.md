# Frozen SMA10 Trend Challenger — Research Report

## Status

**Decision: retain as a prospective challenger; do not promote to the live allocation.**

This report evaluates the pre-registered `trend-sma10-minus20-v1` policy. The rule was frozen in commit `bffe1536e7ff0752f4798f07767d39d2b89718b1` before this historical comparison was run.

Nothing in this research changes the live model, current recommendation, model parameters, or the existing prospective evidence ledger.

## Frozen rule

At each monthly decision:

1. Use the previous completed month's NIFTY 50 price close.
2. Compare it with the arithmetic mean of the latest 10 consecutive completed monthly closes.
3. If the close is **strictly below** the 10-month average, set challenger equity to `max(0, baseline equity - 20 percentage points)`.
4. Otherwise retain the baseline allocation.
5. Equality is risk-on.
6. The trend deduction is not valuation-damped and remains active at valuation extremes.

The 20 percentage-point deduction is a pre-registered test assumption, not a parameter selected after observing results.

## Historical evidence boundary

The historical baseline is the project's fixed-reference **legacy V3.6 valuation core**, not the full modern earnings + macro model. The historical valuation series also crosses NSE accounting-methodology regimes documented elsewhere in the repository. Consequently this is exploratory challenger evidence, not a historical validation of the current full model.

The equity sleeve is NIFTY 50 TRI. The debt sleeve is the exact **NIFTY 10 YR BENCHMARK G-SEC** index. Under NSE Indices' fixed-income convention the index level is total-return; the separately named Clean Price index is not used.

The reproducible automated debt history currently available to this harness begins on **3 January 2011**, so the exact common sample is 2011–2026. No pre-2011 debt returns are fabricated. Official Nifty Indices documentation indicates older historical values exist, but the direct archive endpoint returned the website HTML rather than a machine-readable historical dataset in CI. Therefore the GFC window is explicitly left unavailable rather than estimated from a substitute.

## Reference result

Reference implementation: zero rebalance band, 10 bps one-way turnover cost, annual sleeve expenses of 0.20% equity and 0.15% debt.

| Metric | Legacy valuation baseline | SMA10 challenger | Challenger minus baseline |
|---|---:|---:|---:|
| CAGR | 10.18% | 9.73% | **-0.46 pp** |
| Maximum daily drawdown | -14.53% | -13.15% | **+1.37 pp improvement** |
| 95% monthly expected shortfall | -5.21% | -3.87% | **+1.34 pp improvement** |
| Daily Ulcer Index | 3.12% | 2.71% | **0.41 pp better** |
| Longest underwater period | 212 trading days | 250 trading days | **38 days worse** |
| Average equity exposure | 49.10% | 43.45% | -5.65 pp |
| One-way turnover / initial capital | 41.16x | 38.79x | lower |

The challenger was risk-off in **55 of 189 monthly decisions (29.1%)**.

## Pre-registered historical gate

The frozen review gate required an overall maximum-drawdown improvement of at least **5 percentage points**, with no more than **1 percentage point CAGR sacrifice**.

- Actual drawdown improvement: **1.37 pp — FAIL**.
- Actual CAGR sacrifice: **0.46 pp — PASS**.
- Historical evidence may not promote the challenger automatically under any circumstance.

The most important conclusion is therefore not that trend failed completely. It is that the fixed 20 pp overlay **improved several risk measures consistently but did not improve full-sample maximum drawdown enough to clear the pre-registered hurdle**.

## Stress episodes

| Window | Baseline MDD | Challenger MDD | Improvement |
|---|---:|---:|---:|
| Global Financial Crisis | unavailable | unavailable | Exact debt history not reproducible for this period |
| 2013–2014 taper period | -13.61% | -13.15% | +0.46 pp |
| 2019–2021 / COVID | -11.26% | **-6.59%** | **+4.67 pp** |
| 2022 rates shock | -10.25% | -9.49% | +0.77 pp |

COVID is the strongest historical argument for the overlay. It materially reduced the crash drawdown while giving up only a modest amount of cumulative return over the stress window. But one strong episode is not sufficient evidence for live promotion.

## Is the benefit merely lower equity exposure?

No. The challenger's realized average equity exposure was about **43.45%**. A static monthly-rebalanced portfolio set to the same 43.45% equity exposure produced:

- CAGR: **8.25%** versus challenger **9.73%**.
- Maximum drawdown: **-16.48%** versus challenger **-13.15%**.
- Ulcer Index: **2.98%** versus challenger **2.71%**.
- Longest underwater period: 277 versus challenger 250 trading days.

This is meaningful positive evidence that timing contributed value beyond simply holding less equity. However, the exposure-matched static portfolio's 95% monthly expected shortfall was marginally better (-3.83% versus -3.87%), so the challenger does not dominate every risk statistic.

## Cost and rebalance-band robustness

The conclusion survives the pre-registered implementation sensitivities:

| Band | One-way cost | MDD improvement | CAGR delta |
|---:|---:|---:|---:|
| 0 pp | 10 bps | +1.37 pp | -0.46 pp |
| 0 pp | 50 bps | +1.63 pp | -0.45 pp |
| 5 pp | 10 bps | +1.56 pp | -0.40 pp |
| 5 pp | 50 bps | +1.82 pp | -0.39 pp |

The 5 pp implementation band reduces turnover without changing the qualitative result. It remains a sensitivity specified before the historical comparison, not a new optimized live rule.

## Benchmarks

For the same 2011–2026 common sample:

- NIFTY 50 TRI buy-and-hold: **10.22% CAGR, -38.27% MDD**.
- 60/40 monthly rebalanced: **8.86% CAGR, -22.90% MDD**.
- Legacy valuation core: **10.18% CAGR, -14.53% MDD**.
- SMA10 challenger: **9.73% CAGR, -13.15% MDD**.

The valuation baseline already removes a large amount of equity drawdown relative to buy-and-hold. That partly explains why a second defensive overlay has less room to improve total drawdown.

## Cash-flow companions

These are account-path scenarios, not return calculations. A simple terminal/start CAGR is deliberately not reported because contributions or withdrawals make that statistic invalid.

### SIP

Starting capital ₹10 lakh plus ₹10,000 at subsequent monthly execution dates:

- Total subsequent contributions: ₹18.80 lakh.
- Baseline terminal value: **₹89.44 lakh**.
- Challenger terminal value: **₹85.15 lakh**.

The challenger preserves less terminal wealth, consistent with its lower average equity exposure, while showing a milder account-value stress path.

### Retirement withdrawals

Starting capital ₹10 lakh, initial annual withdrawal 4%, withdrawals inflated by 6%:

- Total withdrawals in each path: about **₹10.26 lakh**.
- Withdrawal shortfall: **zero** in both paths.
- Baseline terminal value: **₹24.82 lakh**.
- Challenger terminal value: **₹22.46 lakh**.
- Account-path MDD: baseline -16.97%, challenger -14.11%.

The challenger provides better path protection but leaves less terminal capital. Its longest retirement account underwater period is also longer, so it is not an unambiguous retirement improvement.

## Interpretation

### Evidence in favor

The fixed trend overlay consistently reduces maximum drawdown across all pre-registered cost/band sensitivities, materially improves expected shortfall and Ulcer Index, substantially helps in the COVID shock, and beats a static portfolio matched to its lower average equity exposure on CAGR, maximum drawdown and Ulcer Index.

### Evidence against promotion

The full-sample maximum-drawdown improvement is only **1.37 pp**, far below the frozen **5 pp** hurdle. CAGR is lower by about 0.46 pp, the longest full-sample underwater period is longer, SIP and retirement terminal wealth are lower, the exposure-matched static comparator has marginally better expected shortfall, and the exact-debt reproducible history does not include the GFC.

## Governance decision

**Keep `trend-sma10-minus20-v1` as a separate prospective challenger. Do not change the live model.**

Historical evidence supports continued observation; it does not support promotion. The frozen prospective process remains controlling. The earliest process review date does not override the separate requirement for at least 60 completed prospective months, and neither condition is an automatic promotion trigger.

The next useful evidence is therefore prospective behavior during genuinely adverse markets, not retrospective tuning of 10 months, 20 percentage points, or the moving-average rule.
