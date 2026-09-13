# Independent robustness audit — updated 13 September 2026

**The evidence does not establish that the live rule is an optimal portfolio or that changing equity exposure through time reliably beats a simpler investable policy.** V3.11 changes the live risk-control policy; it does not turn weak timing evidence into strong timing evidence.

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
- **Timing claim:** moving that exposure through time adds return or improves risk-adjusted performance beyond a simpler policy.
- **Insurance claim:** the SMA10 brake deliberately gives up some expected participation in exchange for crash-path risk reduction; its premium and protection must therefore be disclosed together.

The live site publishes the first and applies the third as an owner-approved policy choice. The available historical evidence does **not** establish the second.

## The DSR/PBO coherence correction

An external review correctly identified that the previous **98.4% Deflated Sharpe probability** was inconsistent with a **61.3% circular-shift percentile** and **57.1% CSCV/PBO**. Inspection confirmed the cause: DSR and CSCV had been run on **total strategy returns**, so the DSR could inherit the return of being substantially long Indian equities rather than isolate timing skill.

The evaluator has therefore been corrected so every candidate is first compared with a static portfolio at that candidate's own realised mean equity exposure. DSR and CSCV/PBO now use only the resulting **timing residual**:

`dynamic net return − same-mean-equity static net return`

The expected-maximum Sharpe threshold was also corrected to include the cross-trial **mean** Sharpe as well as dispersion across the 24 comparable curve variants. Skew and kurtosis in the finite-sample correction come from the selected timing-residual series itself; the selection threshold comes from the full comparable trial family.

A probability of **47.30%** here should **not** be read as a Bayesian posterior statement that there is a 52.7% probability the true Sharpe is negative. It means the selected residual Sharpe does not clear the selection-adjusted expected-maximum benchmark and supplies no positive evidence of timing skill under this diagnostic.

### Corrected timing-skill evidence

| Diagnostic | Corrected result | Gate | Interpretation |
|---|---:|---:|---|
| Exposure-matched timing edge | +0.16 pp/year | > 0 | Positive but economically small |
| Circular-shift placebo percentile | **61.29%** | ≥95% | **Fail** |
| AR(1) surrogate-signal percentile | **62.78%** | ≥95% | **Fail** |
| Deflated Sharpe probability on timing residual | **47.30%** | ≥95% | **Fail** |
| CSCV probability of backtest overfitting on timing residual | **70.0%** | ≤10% | **Fail** |
| Paired 3/6/12-month block-bootstrap lower bounds | Cross zero | >0 for all | **Fail / inconclusive** |

**Over the tested window, moving equity exposure added 0.16 pp/year of return and 1.0 pp of additional drawdown.**

That sentence is intentionally stronger and more useful than saying only that the result is statistically inconclusive: on the tested risk-adjusted comparison, the observed trade-off is slightly unfavourable.

Once equity beta is removed, DSR, PBO and both placebo families tell a coherent story: **on the available 63-month sample, the timing component is not distinguishable from noise at the project's pre-declared evidence thresholds.**

## The exposure-matched null is useful but ex-post

The 53.54% static comparator is deliberately retained because it removes the dynamic strategy's average equity beta. However, 53.54% is the **full-sample realised mean exposure**, so an investor could not have known that weight at the beginning of the sample. It is an attribution diagnostic, not an investable starting portfolio.

The companion benchmark audit therefore adds two information-available-at-the-time nulls:

| Comparator | Ex-ante? | Avg equity | Dynamic minus comparator CAGR | Dynamic additional max drawdown |
|---|---|---:|---:|---:|
| Full-sample realised-mean static | No | 53.54% | **+0.16 pp/yr** | **+1.01 pp** |
| Fixed 60/40 policy | Yes | 60.00% | **-0.25 pp/yr** | **+0.15 pp** |
| Expanding-mean policy | Yes | 39.87% | **+2.11 pp/yr** | **+1.25 pp** |

Against a simple pre-declared 60/40 policy, the dynamic valuation rule earned about **0.25 percentage point less per year** and had about **0.15 percentage point more maximum drawdown** over the same window.

The expanding-mean comparator is implementable because each month's comparator weight uses only allocation targets known through that decision date. The dynamic rule beats it on CAGR, but the expanding comparator averaged only **39.87% equity** versus **53.54%** for the dynamic strategy. Its +2.11 pp result is therefore **not a clean timing-alpha estimate**; a meaningful part of the difference is exposure. This is why the ex-post beta-removal diagnostic and investable policy nulls are shown together rather than pretending one benchmark answers every question.

## Effect size: waiting longer is not the investment thesis

The observed exposure-matched timing residual has a naive monthly t-statistic of about **0.17** across 63 returns.

A purely mechanical square-root-of-time extrapolation would require roughly **709 years** of monthly observations to reach an absolute t-statistic of 2 if the observed effect and variance remained unchanged and observations were independent. Applying the current effective-sample ratio (about 26.5 effective observations from 63 raw observations) stretches that illustration to roughly **1,682 years**.

Neither figure should be taken literally. Stationarity over centuries is not credible. Their purpose is the opposite: **the currently observed effect is too small to justify saying that more calendar time is the remedy.**

The prospective first-seen ledger remains valuable because it can detect a **materially larger, stable edge** if one emerges and creates a tamper-resistant record if it does not. It is no longer framed as a path by which a tiny retrospective point estimate will inevitably become proven.

## Why the AR(1) null matters

The circular-shift placebo keeps the exact observed target-weight path and breaks its calendar alignment with returns. Because it rotates the same path, it already preserves the target-weight distribution and target-path turnover structure; a second random-weight placebo designed only to match mean exposure and turnover would add little.

The more informative second null asks a different question: **would almost any persistent mean-reverting signal have looked similarly useful?**

The evaluator fits a Gaussian AR(1) process to the observed valuation composite's mean, variance and lag-1 persistence, simulates **5,000** surrogate valuation paths, feeds every path through the same live valuation curve, uses the same next-month equity/debt returns and transaction-cost convention, and compares each result with its own exposure-matched static portfolio.

The actual valuation signal ranks only at about the **62.8th percentile** of this surrogate family on excess CAGR. That is mildly above median, but nowhere near the pre-declared 95th-percentile hurdle. The available sample does not show that this particular valuation timing path is meaningfully more informative than a generic persistent signal with similar first-order structure.

## Price of the SMA10 brake: insurance, not alpha

The SMA10 rule is live by explicit owner-approved policy override despite failing its historical automatic-promotion hurdle. That can be a legitimate insurance choice, but insurance has a premium. The project now discloses the premium beside the protection rather than insulating the rule from the evidence standard.

| Frozen SMA10 −20 pp rule | CAGR premium paid | Max daily drawdown avoided | Monthly ES improvement | Ulcer-index improvement | Avg equity reduction | Underwater change |
|---|---:|---:|---:|---:|---:|---:|
| Same 63 calendar return months | **0.09 pp/yr** | **0.77 pp** | **0.98 pp** | **0.19 pp** | **4.69 pp** | +3 trading days |
| Longest exact shared history, 2011–Sep 2026 | **0.46 pp/yr** | **1.37 pp** | **1.34 pp** | **0.41 pp** | **5.65 pp** | +38 trading days |

On the shorter 63-month calendar window the brake cost about **0.09 pp/year** of CAGR to avoid about **0.77 pp** of maximum daily drawdown. On the longer exact shared history it cost about **0.46 pp/year** to avoid about **1.37 pp** of maximum daily drawdown. The longer history also improved expected shortfall and the Ulcer Index, but extended the longest underwater spell by 38 trading days.

The longer study's pre-registered hurdle required at least **5 percentage points** of overall drawdown improvement; the observed improvement was only **1.37 points**, so historical evidence did **not** qualify the rule for automatic promotion. It remains live only as a transparent policy insurance choice, not because the historical gate was reinterpreted after the result.

The two windows use the frozen trend engine's first-shared-trading-close execution convention. The 63-month row matches the timing audit's calendar return months but is not numerically identical to its month-end return convention. Taxes are excluded and the debt sleeve is the long-duration NIFTY 10 YR BENCHMARK G-SEC index.

## Trial-count policy and production lineage

The exact DSR/PBO family currently contains **24 valuation-curve variants** because those are the reproducible hypotheses sharing the same objective, return definition and exact 63-month outcome matrix. The broader registry contains more than 500 other experiments with different eligible windows or asset universes.

The important rule is now explicit: **intent is not a statistical category.** Calling a hypothesis a production version, research variant, challenger or bug fix neither automatically includes nor exempts it. If a numbered production version materially changed an investment hypothesis and was evaluated against the same comparable outcome sample, it consumes a trial in that family.

The current lineage audit found:

- V3.5/V3.6 principally changed macro-data completeness, block structure and macro authority. There is no certified same-window historical macro/earnings stack, so those versions cannot currently be represented as comparable columns in the 63-month valuation-core matrix.
- V3.10 changed the P/B methodology-regime calibration and has a different eligible calibration history; it remains a separately disclosed calibration family rather than being silently pooled into the legacy matrix.
- V3.11 changed cheap-side overlay authority and added the SMA10 policy brake. The full macro/earnings history is not reconstructable on the same certified window, and the SMA10 rule has its own separately governed exact-history study.
- Any earlier or future production version that is reconstructed as a materially different strategy on the exact same outcome matrix **must increase the comparable-family trial burden before the next DSR/PBO promotion claim**.

Accordingly, 24 remains the current exact-family count because no additional production-lineage strategy has yet been demonstrated on that exact common matrix—not because production versions receive an intent-based exemption.

A covariance-aware Mahalanobis valuation composite remains registered as a **challenger only**. If implemented on a comparable common sample, it must increase the relevant candidate-family burden and pass the same evaluator before any promotion review.

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

## Model-design limits that remain

The valuation lenses are correlated. P/E, P/B/profitability, earnings yield versus bonds and dividend yield are not four independent experiments. The strict evaluator measures this redundancy, but the live composite still uses transparent fixed weights rather than a covariance-aware alternative.

The fair-value references are also not proven stationary. V3.10 corrected the P/B methodology regime and V3.11 retains that calibration, but a regime-corrected 36-month sample is still a short anchor.

V3.11's asymmetric overlay authority and trend brake reduce one important crash pathology, but they do not make macro coefficients causal, complete, or statistically validated.

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
| Valuation-core historical timing audit | Legacy fixed-reference reconstruction | Small unfavourable risk-adjusted trade-off; timing skill not established |
| SMA10 trend rule | Live in V3.11 as policy insurance | Premium now disclosed; historical automatic-promotion hurdle failed |
| Gold/Silver/BTC layer | Multi-asset research-v1 | Separate research layer; not validated as an investable after-tax portfolio |

## Remaining work that can materially improve evidence

The next recoverable gains are not another live allocation tweak. They are:

1. Continue the prospective first-seen ledger as a detector of a **materially larger** stable effect, not as a promise that the current tiny effect will eventually become significant.
2. Build an Indian after-tax, instrument-level implementation study with explicit TER, tracking error, exit loads and tax-lot assumptions.
3. Replace flat release-lag sensitivities with per-series historical release calendars wherever public dates can be reconstructed reliably.
4. Continue reconstructing the production-version hypothesis ledger; any comparable historical hypothesis must increase the correct trial family.
5. Evaluate any Mahalanobis/covariance-aware valuation composite only as a registered challenger under the same residual DSR/PBO, circular-shift, AR(1), bootstrap and prospective gates.
6. Keep public wording anchored to what the evidence supports: valuation-based exposure guidance and explicitly priced risk controls, not demonstrated timing alpha.

The normal refresh pipeline publishes `data/robust_evaluation.json` and `data/benchmark_audit.json`. A separate governed workflow publishes `data/sma10_insurance_audit.json`, so timing and insurance diagnostics are inspectable rather than inferred from prose.

## Verification

The expanded audit suite passed **78 Python tests and 24 JavaScript tests**, followed by successful builds of the residual DSR/PBO evaluator, investable benchmark audit and SMA10 insurance-pricing audit. The live model remains fail-closed on stale or inconsistent inputs. Passing implementation tests is necessary, but it is not evidence of investment performance.
