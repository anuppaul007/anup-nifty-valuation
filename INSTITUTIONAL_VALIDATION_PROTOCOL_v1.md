# Institutional Validation Protocol v1 — Anup Nifty Valuation

**Status:** pre-registration framework; research only; zero automatic live authority.

This protocol defines what must be true before this project may use language such as **validated timing residual**, **institutionally validated allocation rule**, or equivalent. It does not assert that the current model has met those standards. V3.13 remains an experimental valuation anchor with separately disclosed policy overlays and adverse evidence.

## 1. Controlling principle

The objective is not to maximize a backtest. The objective is to determine whether a valuation-driven equity/debt rule has reproducible decision value after removing ordinary equity beta, using point-in-time data, realistic implementation assumptions, honest trial counting, and independent challenge.

The controlling object is an immutable commit SHA. Before any outcome analysis under this protocol begins, record the commit SHA containing this file, `institutional_validation_protocol_v1.json`, the certified data specification, trial-family specification, evaluator, and tax/cost assumptions. Once outcomes are inspected, any material change to signal definitions, curve authority, benchmark construction, costs, tax treatment, or statistical gates creates a new protocol/trial version. It may not silently reuse the same outcome sample as untouched evidence.

## 2. Claims are separated

The project must never collapse the following into one score:

1. **Data integrity:** can every signal input be reconstructed using information actually available by the decision date?
2. **Valuation-anchor quality:** does the signal measure relative expensiveness/cheapness coherently and monotonically?
3. **Timing efficacy:** does changing equity exposure add return or risk-adjusted value beyond the equity exposure taken?
4. **Insurance value:** does a trend/risk brake buy useful drawdown protection at an acceptable return premium?
5. **Implementation value:** does any apparent edge survive realistic turnover, TER/tracking difference, slippage and a declared tax profile?
6. **Operational reliability:** does the live system fail closed on stale, malformed, mismatched or semantically ambiguous data?

Strong engineering or reproducibility cannot compensate for weak timing evidence. A risk brake may remain an explicit owner policy choice without being called alpha.

## 3. Primary timing claim

The pre-registered efficacy claim is:

> A valuation-core-only equity/debt allocation rule produces a positive and economically material timing residual after equity-exposure matching, realistic implementation frictions, honest multiple-testing correction and certified point-in-time inputs.

A historical pass under this protocol makes a candidate **eligible for independent/forward confirmation**. It does **not** by itself authorize production replacement of V3.13, because existing model lineage has already been informed by historical market evidence.

## 4. Certified point-in-time sample

No promotion-grade timing test may use a row whose economic input lacks:

- observation/economic period date;
- first-available date/time or conservative availability date;
- source identity and hash;
- methodology regime/version;
- exact transformation version;
- explicit missing/stale/ambiguous status.

Target certified history is **at least 180 completed monthly decisions**. The minimum sample for any validation-language review is **120 completed monthly decisions**. A shorter sample may be reported as research only.

The panel must be versioned and reproducible. Definition breaks, including index valuation methodology changes, may not be bridged by undocumented scaling or hindsight normalization.

## 5. Outcome matrix

All comparable valuation-core variants must be evaluated on the exact same eligible monthly decision matrix.

### Equity sleeve

Use a total-return NIFTY 50 representation. The signal-efficacy layer should use a clean total-return benchmark; an implementation layer must separately map that exposure to an investable vehicle with period-appropriate TER, tracking difference, slippage and availability.

### Debt sleeve

The primary debt sleeve must represent **dry powder / low-duration defensive capital**, not a duration-timing bet. Select and freeze the debt series before strategy returns are inspected, using objective criteria such as sovereign/very-high-quality exposure, short duration, continuity and investability. Do not choose between liquid, T-bill or short-gilt candidates based on which improves the backtest.

If a continuous investable series is unavailable for an early period, a conservative cash/short-sovereign proxy may be used only with an explicit regime flag and sensitivity analysis.

### Rebalancing

Primary implementation uses a pre-registered rebalance-band rule rather than frictionless continuous targeting. Test 0, 5 and 10 percentage-point bands as implementation sensitivities; one primary band must be frozen before outcome inspection. Band alternatives are implementation sensitivities and must not be cherry-picked as new alpha hypotheses.

## 6. Costs and taxes

### Costs

Primary trading-friction assumption: **15 bps one-way on traded notional**, with 10 bps and 25 bps sensitivities. Add instrument-specific TER and tracking difference where the implementation vehicle requires them. Costs are charged only on actual trades, not on portfolio value.

### Tax profiles

There is no universal “Indian after-tax return.” Tax depends on investor type, vehicle, realization path, holding period and historical law. Therefore:

- pre-tax net-of-cost results are always published;
- every after-tax result names a versioned investor/vehicle tax profile;
- historical rates/rules are applied by effective date, with source references;
- realized gains must be lot-aware under the chosen accounting convention;
- loss offsets/carry-forwards, grandfathering, surcharge/cess and dividend treatment must be explicitly included or explicitly excluded;
- if the tax engine is incomplete for a period, that after-tax result is informational and cannot be the sole basis for promotion.

Tax assumptions may reduce an apparent edge; they may not be tuned to improve it.

## 7. Nulls and beta removal

Every candidate must be compared with all of the following under the same return/cost conventions:

1. **Ex-post exposure-matched static diagnostic:** fixed equity weight equal to the candidate's full-sample realized mean equity exposure. This removes beta descriptively but is not investable at sample start.
2. **Investable expanding-mean null:** at each decision, the comparator uses only allocation history available through that decision.
3. **Predeclared fixed 60/40:** monthly or band-rebalanced under the same convention.
4. **NIFTY 50 total-return buy-and-hold:** market beta reference, not a timing-matched null.

No timing claim may rely only on beating 60/40 or buy-and-hold. A candidate must demonstrate residual value after exposure matching and must disclose performance versus at least one information-available-at-the-time null.

## 8. Primary and companion outcomes

### Primary economic outcome

The primary economic effect is the **annualized geometric return difference** between the dynamic valuation core and the ex-post exposure-matched static comparator, after the primary cost convention. The same comparison is also reported under the declared after-tax profile when that tax engine is complete.

**Economic materiality gate:** residual CAGR must be at least **+0.80 percentage points per year** after primary costs. This is a pre-registered hurdle, not a point estimate target.

### Primary inferential outcome

For inference, use the paired monthly residual-return series. The primary inferential test is dependence-aware paired block resampling/permutation with a predeclared block-length rule and family-wise multiple-testing adjustment across every comparable candidate on the matrix.

Required inferential gates:

- family-wise adjusted one-sided significance level <= 5%;
- paired block-bootstrap 95% lower confidence bound for the annualized residual effect > 0;
- the economic +0.80 pp/year hurdle above is also met.

A circular-shift/randomized-signal test is a mandatory robustness diagnostic and should reach at least the 95th percentile for a strong historical claim, but it does not replace the paired block test.

### Companion outcomes

Always publish:

- residual Sharpe and information ratio;
- strategy and comparator CAGR;
- maximum daily drawdown;
- Calmar ratio;
- Ulcer index;
- 95% monthly expected shortfall;
- longest time under water;
- average and distribution of equity exposure;
- annualized one-way turnover;
- number and size of trades;
- terminal wealth sensitivity to costs/taxes.

A drawdown improvement caused only by lower average equity exposure is not timing skill.

## 9. DSR and CSCV/PBO

Deflated Sharpe Ratio and CSCV/Probability of Backtest Overfitting are mandatory **diagnostics** for a comparable trial family when they are estimable. They are not allowed to create false precision.

Before using either as a hard promotion gate, the evaluator must document that the sample length, candidate count and partition design are adequate and that the estimate is reasonably stable to permitted block/partition choices. If adequacy is not demonstrated, report the statistic as **not decision-grade** rather than treating an unstable estimate as a pass or fail.

When decision-grade, the preferred supporting standards are:

- Deflated Sharpe probability >= 95%;
- CSCV/PBO <= 10%.

The primary family-wise block-resampling gate in Section 8 remains controlling even when DSR/PBO are available.

## 10. Trial family and multiple testing

The first certified-panel valuation-core family may contain **no more than six pre-registered comparable variants**. Existing comparable production-lineage hypotheses evaluated on the same matrix also consume family count; calling a rule “control”, “bug fix”, “research”, or “production” does not exempt it.

The planned first family should be compact and economically interpretable, with exact formulas frozen in a separate machine-readable trial specification before outcome inspection. Candidate themes may include:

- equal-weight three-lens core: earnings-yield spread, profitability-adjusted log P/B, dividend yield;
- earnings-yield-spread dominant three-lens core;
- two-lens ablation;
- current V3.13 valuation-core weights as a control;
- at most one predeclared smoothing variant.

The exact bond-yield definition, any inflation adjustment, z-score calibration, weights, curve slope/extreme thresholds and smoothing rule must be fixed before returns are evaluated. No “best” alternative may be added after results are seen without increasing the family and creating a new trial version.

## 11. Core signal design rule

The challenger programme should prefer **fewer, less-redundant valuation lenses**. Redundancy diagnostics must include at least cross-lens correlation, condition/effective-rank information and an economic explanation of shared denominators.

The current monotone P/B profitability correction may remain as a structural accounting transformation, but its coefficients may not be re-optimized on strategy returns.

A valuation-core-only version must exist with no earnings overlay, no macro authority and no trend brake. This is the baseline object for timing-efficacy testing.

## 12. Overlays are separate experiments

### Trend / SMA brake

Treat the trend brake as **insurance unless and until it independently earns an alpha claim**. Publish the premium paid and protection received, including the five largest baseline drawdown episodes, engage/disengage dates and recovery participation. It may not improve the valuation-core timing statistic by being bundled into the core.

### Earnings overlay

Any tactical earnings overlay is a separate challenger with its own point-in-time data, trial count and promotion evidence.

### Macro

Macro retains zero live authority unless a separately pre-registered certified-vintage or prospective macro-on versus macro-off test earns it. Macro context may be displayed without being granted allocation authority.

## 13. Historical pass is not automatic production promotion

This protocol deliberately rejects the rule “one historical hypothesis passes, therefore it becomes production.”

A candidate that clears the certified historical matrix becomes **confirmation-eligible**. Before timing-alpha or institutional-validation language is used, all of the following are additionally required:

1. independent reimplementation of the valuation engine and residual evaluator by a reviewer not previously involved in development;
2. no unresolved critical/high finding affecting the claim;
3. exact reproduction of the frozen historical result within declared numerical tolerances;
4. an untouched confirmation source. For legacy-developed rules, the preferred confirmation is the prospective ledger under a frozen rule; the existing governance minimum of **60 completed prospective months before a promotion review** remains controlling. A demonstrably untouched chronological holdout may supplement this but may not be labelled untouched merely because it was withheld by code after the developers already inspected its strategy outcomes elsewhere.

A historical pass can justify continued research and a frozen challenger. It does not erase model-selection history.

## 14. Independent review trigger

External review begins after the following are frozen:

- certified point-in-time panel version/hash manifest;
- exact trial family;
- cost and tax profiles;
- debt/equity return series rules;
- evaluator code and statistical gates;
- source reconstruction rules.

The external reviewer must independently implement at least the valuation-core transformation and the paired residual evaluator. Calling another AI model, CI run, or author-written duplicate implementation “independent review” is prohibited.

## 15. Claims language hierarchy

Use only language supported by the evidence state:

- **Valuation anchor** — permitted when the current valuation calculation is reproducible and internally coherent.
- **Experimental allocation rule** — permitted while efficacy remains unproven.
- **Historical timing residual** — only when a certified historical matrix clears the pre-registered historical gates; must still disclose model-selection limitations.
- **Insurance overlay** — for a risk brake priced separately from alpha.
- **Validated timing residual / institutionally validated allocation** — reserved for the full historical, independent-review and confirmation requirements above.

If no candidate clears the gates, publish the conclusion directly:

> Current valuation timing residual is not distinguishable from noise after realistic frictions under the frozen protocol; retain the model as a transparent valuation anchor and continue prospective evidence collection.

## 16. Retirement and implementation stress tests

These do not prove alpha but are mandatory before using the tool for retirement allocation decisions:

- lump-sum versus staged deployment with undeployed capital earning the debt return;
- equal monthly contributions;
- inflation-linked withdrawals under multiple start dates;
- sequence-of-returns stress;
- extreme valuation regimes including 0% and 100% equity endpoints where permitted by policy;
- crash/recovery episodes;
- stale-data/source outage simulations.

## 17. Current project state under this protocol

At adoption of v1:

- the historical timing evidence is not eligible for promotion;
- current-definition reconstruction work remains a data-lineage project, not efficacy validation;
- the trend brake is policy insurance, not validated alpha;
- macro has zero live authority;
- V3.13 remains unchanged by this protocol;
- no new valuation core receives live authority merely because this document exists.

## 18. Sequence of work

1. Finish current-definition constituent reconstruction and accounting-semantic gates without opening the sealed holdout prematurely.
2. Build the longest certifiable point-in-time historical input panel and its source/hash manifest.
3. Freeze the investable equity/debt outcome series, cost model and tax-profile specification.
4. Freeze the compact valuation-core trial family and exact formulas.
5. Run the common-matrix historical evaluation once under the family-wise gates.
6. Publish favorable and unfavorable results together.
7. Trigger independent reimplementation.
8. Keep any passing challenger frozen while prospective confirmation accrues; do not auto-promote from the historical backtest.

The institutional objective is a process that can survive a negative result, not a process designed to manufacture a winner.
