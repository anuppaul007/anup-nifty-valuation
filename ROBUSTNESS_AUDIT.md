# Independent robustness audit — updated 13 September 2026

**The evidence does not establish that the live rule is an optimal portfolio or that changing equity exposure through time reliably beats a simpler exposure-matched static allocation.** V3.11 changes the live risk-control policy; it does not turn weak timing evidence into strong timing evidence.

## Current live model: V3.11 crash-aware

The live engine is `3.11-crash-aware-1`.

For the published 11 September 2026 NIFTY observation, the current components are approximately:

- Valuation core: **80.80% equity**.
- Earnings-cycle adjustment: **-1.76 percentage points**.
- Macro adjustment: **-0.24 percentage points**.
- SMA10 crash guard: **-20.00 percentage points** because the completed August NIFTY close, 24,080.4, is below its 10-month average of 24,503.83.
- Live equity/debt signal: **58.81% / 41.19%** before the separate Gold/Silver research layer.

Two V3.11 risk controls are live:

1. When valuation is below reference, the bounded macro and earnings overlays retain full authority instead of being damped toward zero as valuation becomes cheaper.
2. The frozen `trend-sma10-minus20-v1` rule is a one-way brake: risk-off subtracts 20 percentage points from equity; it never adds equity. Missing or stale trend data withhold the allocation.

This fixes a specific structural pathology in the earlier model where an extreme-cheap valuation endpoint could coexist with effectively zero macro authority. It does **not** prove that the new policy adds alpha or prevents gap risk.

## What the published percentage means

The live percentage is best interpreted as a **valuation-based allocation anchor with bounded earnings, macro and trend risk controls**.

That is deliberately different from claiming that the model has proven market-timing skill.

- **Anchor claim:** current valuation maps transparently into an equity/debt exposure under frozen assumptions.
- **Timing claim:** moving that exposure through time adds return or improves risk-adjusted performance beyond a static portfolio with the same average equity exposure.

The live site publishes the first. The available historical evidence does **not** establish the second.

## The DSR/PBO coherence correction

An external review correctly identified that the previous **98.4% Deflated Sharpe probability** was inconsistent with a **61.3% circular-shift percentile** and **57.1% CSCV/PBO**. Inspection confirmed the cause: DSR and CSCV had been run on **total strategy returns**, so the DSR could inherit the return of being substantially long Indian equities rather than isolate timing skill.

The evaluator has therefore been corrected so every candidate is first compared with a static portfolio at that candidate's own realised mean equity exposure. DSR and CSCV/PBO now use only the resulting **timing residual**:

`dynamic net return − same-mean-equity static net return`

The expected-maximum Sharpe threshold was also corrected to include the cross-trial **mean** Sharpe as well as the dispersion across the 24 comparable curve variants. Skew and kurtosis in the finite-sample DSR correction come from the selected timing-residual series itself; the selection threshold comes from the full comparable trial family.

### Corrected timing-skill evidence

| Diagnostic | Corrected result | Gate | Interpretation |
|---|---:|---:|---|
| Exposure-matched timing edge | Positive, small | > 0 | Necessary, not sufficient |
| Circular-shift placebo percentile | **61.29%** | ≥95% | **Fail** |
| AR(1) surrogate-signal percentile | **62.78%** | ≥95% | **Fail** |
| Deflated Sharpe probability on timing residual | **47.30%** | ≥95% | **Fail** |
| CSCV probability of backtest overfitting on timing residual | **70.0%** | ≤10% | **Fail** |
| Paired 3/6/12-month block-bootstrap lower bounds | Cross zero | >0 for all | **Fail / inconclusive** |

The previous 98.4% DSR should therefore **not** be used as evidence of timing skill. Once equity beta is removed, DSR, PBO and both placebo families tell a coherent story: **on the available 63-month sample, the timing component is not distinguishable from noise at the project's pre-declared evidence thresholds.**

This is a correction to the evidence plumbing, not a change to the live allocation formula.

## Why the AR(1) null matters

The circular-shift placebo keeps the exact observed target-weight path and breaks its calendar alignment with returns. Because it rotates the same path, it already preserves the target-weight distribution and target-path turnover structure; a second random-weight placebo designed only to match mean exposure and turnover would add little.

The more informative second null asks a different question: **would almost any persistent mean-reverting signal have looked similarly useful?**

The evaluator now fits a Gaussian AR(1) process to the observed valuation composite's mean, variance and lag-1 persistence, simulates **5,000** surrogate valuation paths, feeds every path through the same live valuation curve, uses the same next-month equity/debt returns and transaction-cost convention, and compares each result with its own exposure-matched static portfolio.

The actual valuation signal ranks only at about the **62.8th percentile** of this surrogate family on excess CAGR. That is mildly above median, but nowhere near the pre-declared 95th-percentile hurdle. The result is uncomfortable in exactly the useful way: the available sample does not yet show that this specific valuation timing path is meaningfully more informative than a generic persistent signal with similar first-order structure.

## Trial-count policy

The exact DSR/PBO family contains **24 valuation-curve variants** because those variants share the same objective, return definition and common eligible window. The broader research registry contains more than 500 other variants across calibration studies, trend research and the separate multi-asset project.

Those broader experiments remain disclosed in `research_trial_registry.json`, but they are not blindly pooled into one DSR number when they use different asset universes, eligible periods or research objectives. Doing so would create a different statistical error.

Likewise, software bug-fix versions and publication labels are not automatically counted as independent strategy trials unless they represented materially different investment hypotheses evaluated against outcomes.

A covariance-aware Mahalanobis valuation composite is now registered as a **challenger only**. If implemented on a comparable common sample, it must increase the relevant candidate-family burden and pass the same evaluator before any promotion review.

## Corrected historical valuation-core results

The saved common panel uses 10 bps per 100% one-way turnover. Initial acquisition costs and taxes are excluded. Drawdown is measured at month ends, so intramonth losses can be larger. Debt is the NIFTY 10 Year Benchmark G-Sec total-return index and therefore carries meaningful duration risk.

| Same full 63-month return window | CAGR | Monthly-sampled max drawdown | Calmar |
|---|---:|---:|---:|
| Fixed-reference valuation core | 8.92% | -9.60% | 0.929 |
| Monthly rebalanced 60/40 | 9.17% | -9.45% | 0.970 |
| Monthly rebalanced 70/30 | 9.79% | -10.77% | 0.909 |
| 100% NIFTY total-return index | 11.58% | -14.68% | 0.789 |

Those numbers do not establish superiority. The comparable current-methodology sample is short and fixed reference constants were not demonstrably frozen at its start.

## Calibration and publication-lag sensitivity

The repository compares the fixed-reference rule with rolling and expanding alternatives that use only prior observations, and separately tests a two-month bond-yield lag. These alternatives were still designed retrospectively and do not create an untouched out-of-sample sample.

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

It did **not** meet its pre-registered 5 percentage-point overall drawdown-improvement hurdle. Historical evidence therefore did not automatically justify promotion. V3.11 uses it because the project owner explicitly chose the transparent one-way brake as a **risk-control policy** after reviewing that trade-off. It should not be described as proven timing alpha.

## Model-design limits that remain

The valuation lenses are correlated. P/E, P/B/profitability, earnings yield versus bonds and dividend yield are not four independent experiments. The strict evaluator measures this redundancy, but the live composite still uses transparent fixed weights rather than a covariance-aware alternative.

The fair-value references are also not proven stationary. V3.10 corrected the P/B methodology regime and V3.11 retains that calibration, but a regime-corrected 36-month sample is still a short anchor.

V3.11's asymmetric overlay authority and trend brake reduce one important crash-pathology, but they do not make macro coefficients causal, complete, or statistically validated.

## Implementation realism remains a practical gap

The core historical audit includes a 10 bps one-way turnover assumption, but it excludes investor-specific Indian taxation. The multi-asset history uses synthetic INR Gold/Silver/BTC market-price series rather than exact Indian ETF total returns and therefore omits fund TER, tracking error, exit loads, bid/ask effects and tax-lot consequences.

No after-tax superiority claim is made.

The importance of this gap depends on the claim being made. If the system is used mainly as a **slow-moving strategic valuation anchor**, turnover should be structurally lower and taxes are less likely to dominate the economic case. If the system is claimed to add value through frequent tactical timing, a detailed after-tax implementation study becomes much more important. Either way, taxes and real instrument costs must be included before claiming taxable-investor net outperformance.

## Data boundary

The scored live set includes US real yields, Fed assets, broad USD, VIX, Brent, India-US nominal yield spread, India REER, USD/INR momentum, India CPI, IIP and repo, and China manufacturing PMI/new orders. **100% data coverage means those defined inputs are currently eligible; it does not mean all relevant economic risk has been measured.**

The project still lacks a complete release-vintage archive for the historical full stack. Fiscal shocks, credit stress, bank liquidity, capital flows, trade balances, geopolitics and sector-specific earnings risks do not have separately validated coefficients.

## Public version matrix

| Surface | Current authority | Historical evidence status |
|---|---|---|
| Live equity/debt allocation | **V3.11 crash-aware** | Prospective; not historically validated as a full stack |
| P/B fair-value calibration | **V3.10 regime correction**, retained in V3.11 | 36 completed current-methodology months |
| Valuation-core historical timing audit | Legacy fixed-reference reconstruction | Timing skill not established; not release-vintage |
| SMA10 trend rule | Live in V3.11 as a policy brake | Historical challenger failed its pre-registered automatic hurdle |
| Gold/Silver/BTC layer | Multi-asset research-v1 | Separate research layer; not validated as an investable after-tax portfolio |

## Remaining work that can materially improve evidence

The next recoverable gains are not another live allocation tweak. They are:

1. Continue the prospective first-seen ledger; real out-of-sample time cannot be compressed by a better backtest.
2. Build an Indian after-tax, instrument-level implementation study with explicit TER, tracking error, exit loads and tax-lot assumptions.
3. Replace flat release-lag sensitivities with per-series historical release calendars wherever public dates can be reconstructed reliably.
4. Evaluate any Mahalanobis/covariance-aware valuation composite only as a registered challenger under the same residual DSR/PBO, circular-shift, AR(1), bootstrap and prospective gates.
5. Keep the public wording anchored to what the evidence supports: valuation-based exposure guidance and explicit risk controls, not demonstrated timing alpha.

The normal refresh pipeline publishes `data/robust_evaluation.json`, so these diagnostics are inspectable rather than inferred from prose.

## Verification

The V2 evaluator and AR(1) null passed the repository CI suite: **75 Python tests and 24 JavaScript tests** were green in the audit PR. The live model remains fail-closed on stale or inconsistent inputs. Passing implementation tests is necessary, but it is not evidence of investment performance.
