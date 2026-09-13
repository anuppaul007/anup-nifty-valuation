# Current model and data audit — V3.11 crash-aware — 13 September 2026

This file is the current operational audit for **Anup Nifty Valuation V3.11**. The original V3.4 audit remains preserved in repository history; this document supersedes its opening status so a reader is not left thinking V3.4 is still the active model.

The live engine is V3.11. Its valuation calibration still inherits the V3.10 P/B regime correction. Legacy V3.6/V3.7 historical studies remain research-only and do **not** constitute a historical release-vintage backtest of V3.11.

## Current live architecture

| Layer | Current role | Live authority |
| --- | --- | --- |
| Valuation core | Long-horizon allocation anchor from P/E, profitability-adjusted P/B, earnings-yield minus G-sec, and dividend yield | Primary driver |
| Earnings cycle | Bounded fundamental overlay | ±6 percentage points |
| Macro | Bounded economic/liquidity overlay with fail-closed data gates | ±6 percentage points |
| SMA10 trend | One-way crash-risk policy brake using the previous completed month | 0 or -20 percentage points |
| Gold / Silver / BTC | Separate multi-asset research layer | Does not redefine the NIFTY valuation engine |

V3.11 deliberately keeps full bounded macro/earnings authority when valuation is below reference; cheap valuations no longer make those stress overlays disappear. The SMA10 rule is a separate risk-control policy and is not claimed as statistically proven timing alpha.

## What the published percentage means

The live equity/debt percentage should be read primarily as a **valuation-based allocation anchor with bounded risk controls**, not as proof that month-to-month timing adds alpha.

Three claims are separated:

1. **Anchor claim:** the current valuation state maps transparently into an equity/debt exposure under frozen model assumptions.
2. **Timing claim:** changing exposure through time beats a simpler policy after accounting for equity exposure, costs and selection.
3. **Insurance claim:** a deliberately asymmetric brake may sacrifice return to reduce crash-path risk, but its premium and protection must be published together.

The first is what the live model primarily publishes. The second remains unproven. The third is how the live SMA10 rule is governed.

## Strict timing-evidence gate

`scripts/robust_evaluation.py` is the governing statistical audit for timing claims. As of the V2 evaluator introduced on 13 September 2026:

- every DSR and CSCV/PBO calculation uses the **exposure-matched timing residual**, not total portfolio returns;
- the ex-post attribution null is a static portfolio at the strategy's realised full-sample mean equity weight;
- that full-sample mean is explicitly labelled **not investable at sample start**;
- `scripts/benchmark_audit.py` additionally compares the strategy with a pre-declared fixed 60/40 policy and an expanding-mean comparator using only targets available through each decision date;
- all non-zero circular shifts of the observed target-weight path form one placebo family;
- a second null uses **AR(1) surrogate valuation composites** calibrated to the observed composite's mean, variance and lag-1 persistence, then passed through the same allocation curve, next-month returns and cost model;
- 3/6/12-month paired moving-block bootstrap intervals are reported on the timing residual;
- Deflated Sharpe and CSCV/PBO are computed only on the exact comparable common-sample candidate family;
- materially different research families remain logged in `research_trial_registry.json` and are not falsely pooled into one DSR statistic.

The key descriptive result is now published directly:

**Over the tested window, moving equity exposure added 0.16 pp/year of return and 1.0 pp of additional drawdown.**

Against a fixed 60/40 investable policy over the same window, the dynamic rule earned about **0.25 pp/year less** and experienced about **0.15 pp more maximum drawdown**. The expanding-mean comparator produced a larger positive return gap for the dynamic rule, but averaged materially less equity and therefore is not a pure timing-alpha null.

The evaluator fails closed. No statistic can automatically modify `model.js`.

## Effect-size interpretation and the prospective ledger

The exposure-matched timing residual's naive t-statistic is about **0.17**. Mechanical square-root-of-time scaling gives roughly **709 years** to reach |t|=2 under independent observations. Applying the observed effective-sample efficiency stretches that illustration to roughly **1,682 years**.

Those figures are not forecasts and assume implausible long-run stationarity. They are included to make the interpretation explicit: **the current observed timing effect is too small for “wait for more data” to be the investment thesis.**

The prospective ledger is therefore governed as a detector of a **materially larger stable effect** if one emerges, and as a tamper-resistant record of its absence otherwise. Sixty completed prospective months remain a necessary minimum before any promotion review, not a promise that statistical validation will arrive at month 60.

## SMA10 policy insurance must publish its price

The frozen SMA10 −20 percentage-point rule remains live by explicit owner-approved policy choice despite failing its pre-registered historical automatic-promotion hurdle. It is therefore treated as crash insurance rather than alpha.

The project now publishes both sides of that trade-off:

- **Same 63 calendar return months:** about **0.09 pp/year CAGR premium paid** for about **0.77 pp of maximum daily drawdown avoided**; expected shortfall improved about 0.98 pp, Ulcer Index about 0.19 pp, average equity fell about 4.69 pp, and the longest underwater spell increased by 3 trading days.
- **Longest exact shared history, 2011–September 2026:** about **0.46 pp/year CAGR premium paid** for about **1.37 pp of maximum daily drawdown avoided**; expected shortfall improved about 1.34 pp, Ulcer Index about 0.41 pp, average equity fell about 5.65 pp, and the longest underwater spell increased by 38 trading days.

The longer-history drawdown improvement remained below the pre-registered **5 pp** hurdle, so the policy override is never described as successful historical promotion or proven timing alpha.

## Trial-count policy

The exact DSR/PBO trial count is the number of **comparable variants on the same objective, return definition and eligible outcome sample**. The broader registry is disclosed separately.

The governing rule is now explicit: **research versus production intent is not a statistical category.** A materially different numbered production hypothesis evaluated on the same outcome matrix consumes a trial just as a deliberately named research variant does.

The present exact family remains at 24 because the currently reproducible V3.x production-lineage changes do not form additional columns on that exact 63-month valuation-core matrix: V3.5/V3.6 changed macro structure without a certified same-window historical macro stack; V3.10 uses a different P/B regime-calibration history; and V3.11 adds overlays/trend that are governed on different historical evidence. If an earlier production hypothesis is reconstructed on the exact same matrix, it must be added before the next DSR/PBO promotion claim.

This prevents two opposite errors:

- understating the burden by pretending only the published winner existed; and
- overstating it by pooling unrelated Gold/Silver/BTC perturbations or different-window calibration studies into the NIFTY timing DSR.

## Data integrity controls

The current production pipeline preserves the main safeguards developed through V3.4–V3.11:

- source failures are isolated rather than replaced by neutral scores;
- required macro coverage must be complete before a final allocation is published;
- stale, future-dated or undated required observations are rejected;
- individual observation dates are preserved instead of relabelling every series with the file-refresh date;
- completed months are used for monthly momentum/cycle calculations;
- duplicate periods and ambiguous multi-series responses are rejected;
- failed browser reads clear the previously displayed allocation rather than leaving stale numbers visible;
- the prospective evidence ledger preserves first-seen observations and does not backdate revised data;
- V3.11 trend data use completed months only and fail closed when history is insufficient or inconsistent.

## Known limitations that remain

The following are **not fixed by better statistics** and remain explicit constraints on interpretation:

- the complete V3.11 valuation + earnings + macro + trend stack lacks certified release-vintage history through 2008 and March 2020;
- the clean current-methodology valuation sample is short;
- current fixed valuation references were not demonstrably frozen at the start of the retrospective sample;
- P/E, P/B, earnings yield and dividend yield are correlated lenses, not four independent pieces of evidence;
- fair-value/reference assumptions remain economically important and sensitivity must be shown rather than hidden;
- the 10 bps one-way transaction-cost convention is not an Indian after-tax investor model;
- ETF/fund TER, tracking error, exit loads, tax lots, capital-gains taxes and instrument-specific liquidity are not yet fully modelled;
- monthly drawdowns can understate intramonth losses;
- an SMA10 brake cannot protect against an overnight gap before the signal can change;
- no historical result is allowed to imply that the system is crash-proof or guaranteed to outperform.

## Multi-asset boundary

Gold and Silver are diversification research sleeves carved from the core allocation; Bitcoin remains outside the retirement-core 100% by design. Their historical research uses synthetic INR conversions and market-price proxies and therefore cannot be described as exact investable after-tax performance. See `MULTIASSET.md`.

## Verification and publication

The repository test suite covers source parsing, stale-data rejection, no-neutral-fill behavior, completed-month logic, drawdown accounting, drift-aware turnover, prospective-ledger integrity, V3.11 cheap-side overlay authority, the one-way -20 pp trend brake, the strict statistical evaluator and investable benchmark diagnostics. The audit PR passed **78 Python tests and 24 JavaScript tests**, plus successful builds of the benchmark and SMA10 insurance audits.

The regular refresh pipeline rebuilds `data/robust_evaluation.json` and `data/benchmark_audit.json`. A separate governed workflow publishes `data/sma10_insurance_audit.json`, so the public evidence surface does not rely on prose alone.

## Historical V3.4 note

The earlier V3.4 audit identified important defects including a wrong STOXX table binding, insufficient calibration handling, stale-data risks, incomplete-coverage treatment, partial-month comparisons and browser stale-state behavior. Those findings drove many of the present fail-closed controls. The full original wording remains available in Git history and should be read as a historical audit, not as the description of the active V3.11 model.

For performance/evidence limitations and retrospective comparisons, see `ROBUSTNESS_AUDIT.md`. For the machine-readable evidence gate, see `data/robust_evaluation.json`.
