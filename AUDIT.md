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

Two claims are separated:

1. **Anchor claim:** the current valuation state maps transparently into an equity/debt exposure under frozen model assumptions.
2. **Timing claim:** changing exposure through time beats a static portfolio at the same average equity exposure.

The first is what the live model publishes. The second is a statistical claim and currently remains **unproven**.

## Strict timing-evidence gate

`scripts/robust_evaluation.py` is the governing statistical audit for timing claims. As of the V2 evaluator introduced on 13 September 2026:

- every DSR and CSCV/PBO calculation uses the **exposure-matched timing residual**, not total portfolio returns;
- the live rule is compared with a static portfolio at its realised mean equity weight under identical equity/debt returns and cost conventions;
- all non-zero circular shifts of the observed target-weight path form one placebo family;
- a second null uses **AR(1) surrogate valuation composites** calibrated to the observed composite's mean, variance and lag-1 persistence, then passed through the same allocation curve, next-month returns and cost model;
- 3/6/12-month paired moving-block bootstrap intervals are reported on the timing residual;
- Deflated Sharpe and CSCV/PBO are computed only on the exact 24-member common-sample valuation-curve family;
- materially different research families remain logged in `research_trial_registry.json` and are not falsely pooled into one DSR statistic.

The evaluator fails closed. No statistic can automatically modify `model.js`.

## Trial-count policy

The exact DSR/PBO trial count is the number of **comparable variants on the same objective, return series and eligible sample**. The broader registry is disclosed separately.

This prevents two opposite errors:

- understating the burden by pretending only the published winner existed; and
- overstating it by pooling unrelated Gold/Silver/BTC perturbations or different-window calibration studies into the NIFTY timing DSR.

Publication version numbers and bug-fix releases are not automatically statistical trials unless they represented a materially different strategy hypothesis evaluated against outcomes.

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

The repository test suite covers source parsing, stale-data rejection, no-neutral-fill behavior, completed-month logic, drawdown accounting, drift-aware turnover, prospective-ledger integrity, V3.11 cheap-side overlay authority, the one-way -20 pp trend brake, and the strict statistical evaluator. The robust-evaluation workflow must pass before audit/evaluator changes are merged.

The regular refresh pipeline also rebuilds `data/robust_evaluation.json`, so the published statistical evidence is not merely a one-off CI artifact.

## Historical V3.4 note

The earlier V3.4 audit identified important defects including a wrong STOXX table binding, insufficient calibration handling, stale-data risks, incomplete-coverage treatment, partial-month comparisons and browser stale-state behavior. Those findings drove many of the present fail-closed controls. The full original wording remains available in Git history and should be read as a historical audit, not as the description of the active V3.11 model.

For performance/evidence limitations and retrospective comparisons, see `ROBUSTNESS_AUDIT.md`. For the machine-readable evidence gate, see `data/robust_evaluation.json`.
