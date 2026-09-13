# Independent robustness audit — updated 13 September 2026

**The evidence still does not establish that the live rule is an optimal portfolio or that it reliably beats a simpler exposure-matched static allocation.** V3.11 changes the live risk-control policy, not the historical evidence standard.

## Current live model: V3.11 crash-aware

The live engine is now `3.11-crash-aware-1`.

For the published 11 September 2026 NIFTY observation, the current components are approximately:

- Valuation core: **80.80% equity**.
- Earnings-cycle adjustment: **-1.76 percentage points**.
- Macro adjustment: **-0.24 percentage points**.
- SMA10 crash guard: **-20.00 percentage points** because the completed August NIFTY close, 24,080.4, is below its 10-month average of 24,503.83.
- Live equity/debt signal: **58.81% / 41.19%** before the separate Gold/Silver research layer.

Two V3.11 risk controls are live:

1. When valuation is below reference, the bounded macro and earnings overlays retain full authority instead of being damped toward zero as valuation becomes cheaper.
2. The frozen `trend-sma10-minus20-v1` rule is a one-way brake: risk-off subtracts 20 percentage points from equity; it never adds equity. Missing or stale trend data withhold the allocation.

This fixes the specific structural pathology in the earlier surface where an extreme-cheap valuation endpoint could coexist with effectively zero macro authority. It does **not** prove that the new policy adds alpha or prevents gap risk.

## The most important sentence on the site

**The historical valuation-timing rule has not yet been shown to beat a static portfolio with the same average equity exposure after costs with sufficient statistical confidence.**

That statement is more informative than a long list of caveats. It should be read before the live percentage.

## What the strict evaluator already tests

The repository's `scripts/robust_evaluation.py` now performs several tests that are not obvious from the older public audit text:

- **Exposure-matched static benchmark.** The dynamic valuation-core portfolio is compared with a static equity weight equal to the dynamic rule's own realised mean equity exposure.
- **Timing decomposition.** The net monthly return difference between dynamic and exposure-matched static portfolios is isolated rather than attributing all return to timing skill.
- **Placebo timing test.** Every non-zero circular shift of the exact target-weight path is tested, preserving the same target-weight distribution while breaking its calendar alignment with returns.
- **Paired moving-block bootstrap.** Timing differences are bootstrapped using 3-, 6- and 12-month blocks and reported with 95% intervals.
- **Deflated Sharpe diagnostic.** The live curve is evaluated against the expected maximum Sharpe from the exact 24-member valuation-curve family.
- **CSCV / PBO.** Eight-slice combinatorially symmetric cross-validation estimates the probability of backtest overfitting for that same 24-member family.
- **Autocorrelation-aware effective sample size.** Persistence in monthly timing differences is made explicit rather than treating every overlapping observation as independent.
- **Lens redundancy.** The correlation matrix and eigenvalue participation ratio estimate how many effectively independent valuation dimensions the four displayed lenses actually contain.
- **Trial registry.** Research families are counted separately rather than pretending only the final published variant was ever tried.

These are useful diagnostics, but they apply to the available valuation-core history. They are **not** a certified release-vintage backtest of the complete V3.11 model with macro, earnings and the live trend guard.

## Corrected historical valuation-core results

The saved common panel uses 10 bps per 100% one-way turnover. Initial acquisition costs and taxes are excluded. Drawdown is measured at month ends, so intramonth losses can be larger. Debt is the NIFTY 10 Year Benchmark G-Sec total-return index and therefore carries meaningful duration risk.

| Same full 63-month return window | CAGR | Monthly-sampled max drawdown | Calmar |
|---|---:|---:|---:|
| Fixed-reference valuation core | 8.92% | -9.60% | 0.929 |
| Monthly rebalanced 60/40 | 9.17% | -9.45% | 0.970 |
| Monthly rebalanced 70/30 | 9.79% | -10.77% | 0.909 |
| 100% NIFTY total-return index | 11.58% | -14.68% | 0.789 |

Those numbers do not establish superiority. The full comparable sample is short and excludes both the 2008 crisis and the March 2020 crash.

## Calibration and publication-lag sensitivity

The repository also compares the fixed-reference rule with rolling and expanding alternatives that use only prior observations, and separately tests a two-month bond-yield lag. These alternatives were still designed retrospectively and do not create an untouched out-of-sample sample.

| Same 27-month return window | CAGR | Monthly-sampled max drawdown |
|---|---:|---:|
| Original fixed references | 7.84% | -9.60% |
| Original references, yield lagged two months | 7.65% | -9.90% |
| Rolling 36-month references, equal lenses | 7.91% | -9.43% |
| Expanding references, equal lenses | 7.29% | -10.36% |
| 60/40 | 5.97% | -9.45% |

Twenty-seven returns cannot establish superiority, and current-vintage monthly data are not equivalent to archived release vintages.

## Trend crash-guard evidence

The frozen SMA10 minus-20 percentage-point challenger was tested on the exact shared NIFTY/debt history available from 2011 onward. In the reference run it improved overall maximum daily drawdown by about **1.37 percentage points** and the COVID-window drawdown by about **4.67 percentage points**, while reducing CAGR by about **0.46 percentage points**.

It did **not** meet its pre-registered 5 percentage-point overall drawdown-improvement hurdle. Historical evidence therefore did not auto-promote the challenger. V3.11 uses it because the project owner explicitly chose the transparent risk brake as a policy control after reviewing that trade-off. That distinction is preserved in the repository.

## Model-design limits that remain

The valuation lenses are correlated. P/E, P/B/profitability, earnings yield versus bonds and dividend yield are not four independent experiments. The strict evaluator measures this redundancy, but the live composite still uses transparent fixed weights rather than a covariance-aware Mahalanobis composite.

The fair-value references are also not proven stationary. V3.10 corrected the P/B methodology regime and V3.11 retains that calibration, but a regime-corrected 36-month sample is still a short anchor.

V3.11's asymmetric overlay authority and trend brake reduce one important crash-pathology, but they do not make macro coefficients causal, complete, or statistically validated.

## Implementation realism remains the largest practical gap

The core historical audit includes a 10 bps one-way turnover assumption, but it still excludes investor-specific Indian taxation. The multi-asset history uses synthetic INR Gold/Silver/BTC market-price series rather than exact Indian ETF total returns and therefore omits fund TER, tracking error, exit loads, bid/ask effects and tax-lot consequences.

No after-tax superiority claim is made. A taxable implementation study should be run separately for at least two containers: a long-term core sleeve and a tactical/rebalancing sleeve, with taxes and real investable instruments applied to actual sale lots rather than as a single annual haircut.

## Data boundary

The scored live set includes US real yields, Fed assets, broad USD, VIX, Brent, India-US nominal yield spread, India REER, USD/INR momentum, India CPI, IIP and repo, and China manufacturing PMI/new orders. **100% data coverage means those defined inputs are currently eligible; it does not mean all relevant economic risk has been measured.**

The project still lacks a complete release-vintage archive for the historical macro stack. Fiscal shocks, credit stress, bank liquidity, capital flows, trade balances, geopolitics and sector-specific earnings risks do not have separately validated coefficients.

## Public version matrix

| Surface | Current authority | Historical evidence status |
|---|---|---|
| Live equity/debt allocation | **V3.11 crash-aware** | Prospective; not historically validated as a full stack |
| P/B fair-value calibration | **V3.10 regime correction**, retained in V3.11 | 36 completed current-methodology months |
| Valuation-core historical timing audit | Legacy fixed-reference reconstruction | Research only; no release-vintage claim |
| SMA10 trend rule | Live in V3.11 as a policy brake | Historical challenger failed its pre-registered promotion hurdle |
| Gold/Silver/BTC layer | Multi-asset research-v1 | Separate research layer; not validated as an investable after-tax portfolio |

## Remaining work that can materially improve the evidence score

The next recoverable gains are not another live allocation tweak. They are:

1. Publish the strict evaluator's exposure-matched benchmark, placebo, block-bootstrap, Deflated Sharpe and CSCV/PBO output alongside the website rather than leaving it in CI artifacts.
2. Add a second placebo family that randomises timing while matching mean exposure **and realised turnover**, with its design frozen before reading results.
3. Build an Indian after-tax, instrument-level implementation study with explicit TER, tracking error, exit load and tax-lot assumptions.
4. Replace the flat two-month historical lag sensitivity with per-series release calendars wherever public release dates can be reconstructed reliably.
5. Continue the prospective first-seen ledger. Time cannot be compressed by a better backtest.

The refresh pipeline now publishes `data/robust_evaluation.json` so these statistical diagnostics can be inspected directly instead of inferred from prose.

## Verification

The live model remains fail-closed on stale or inconsistent inputs. The CI suite covers data parsers, allocation bounds, trend-gate consistency, drift-aware turnover, calendar gaps, evidence freezing and robustness routines. Passing implementation tests is necessary, but it is not evidence of investment performance.
