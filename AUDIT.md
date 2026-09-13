# Current model and data audit — V3.12 evidence-first — 13 September 2026

This file describes the active architecture proposed in PR #17 for **Anup Nifty Valuation V3.12**. Earlier V3.x audits remain preserved in repository history. V3.12 retains the V3.10 P/B regime correction and the frozen V3.11 SMA10 policy brake, but changes macro governance after an explicit evidence/operational-risk audit.

## Current live architecture

| Layer | Current role | Live authority |
| --- | --- | --- |
| Valuation core | Long-horizon allocation anchor from P/E, profitability-adjusted P/B, earnings-yield minus G-sec, and dividend yield | Primary driver |
| Earnings cycle | Bounded fundamental overlay | ±6 percentage points |
| Macro | Verified economic/liquidity context plus prospective shadow challenger | **0 pp live; ±6 pp shadow** |
| SMA10 trend | Frozen one-way crash-insurance policy using the previous completed month | 0 or -20 percentage points |
| Gold / Silver / BTC | Separate multi-asset research layer | Does not redefine the NIFTY valuation engine |

V3.12 therefore computes the live NIFTY equity/debt target as:

`valuation core + earnings adjustment + SMA10 adjustment`

Macro is still fetched, validated, displayed and archived. When every defined macro observation is fresh and internally consistent, the former ±6 pp macro rule is recorded as a **shadow** result. Missing, stale or inconsistent macro context withholds the shadow result, but does **not** change or withhold the live V3.12 allocation.

This is a governance decision under uncertainty, not proof that macro information has zero investment value.

## Why macro moved to shadow

The current macro stack has four top-level blocks and a sizeable external-data/parser surface. On the 11 September 2026 snapshot the overall macro score was about -0.04 and the former V3.11 rule changed equity by only about **-0.24 percentage point**.

The new `scripts/macro_authority_audit.py` asks the decision question that had remained unresolved: what return or drawdown benefit has that live authority purchased, and what operational failure probability should be charged against it?

The answer is deliberately incomplete rather than fabricated:

- a certified release-vintage reconstruction of the full historical macro stack does **not** exist, so a historical macro-on versus macro-off CAGR/drawdown price is **unavailable**;
- current-vintage/revised macro history is not silently substituted and relabelled as point-in-time evidence;
- the repository has previously caught semantic/source problems such as an incorrect STOXX table binding, demonstrating that syntactically plausible source drift is a real failure class;
- a monthly probability of a wrong-but-plausible semantic error is **not identifiable** from a handful of caught incidents because there is no defensible denominator.

With decision value unpriced and operational surface non-trivial, V3.12 gives macro zero live authority while retaining the exact same information as visible context and a prospective ±6 pp shadow challenger. Macro can regain live authority only after a predeclared prospective or certified release-vintage macro-on versus macro-off comparison under identical valuation, earnings, trend, cost and outcome conventions. Any tested alternative macro budget joins its comparable selection family.

## What the published percentage means

The live equity/debt percentage should be read primarily as a **valuation-based allocation anchor with bounded earnings and explicitly priced crash insurance**, not as proof of market-timing alpha.

Four claims are separated:

1. **Anchor claim:** current valuation maps transparently into an equity/debt exposure under frozen assumptions.
2. **Timing claim:** changing exposure through time beats a simpler investable policy after accounting for equity exposure, costs and selection.
3. **Insurance claim:** the SMA10 brake may sacrifice return to reduce crash-path risk; its premium, event payout and recovery drag must be published together.
4. **Macro claim:** economic context may be informative, but live allocation authority remains zero until its incremental decision value is demonstrated.

## Comparator geometry: three rows, one exposure finding

The primary timing window contains 63 monthly returns. The three comparator rows should not be interpreted as independent votes:

| Comparator | Ex-ante? | Avg equity | Dynamic minus comparator CAGR | Dynamic additional max drawdown |
| --- | --- | ---: | ---: | ---: |
| Expanding-mean policy | Yes | 39.87% | +2.11 pp/yr | +1.25 pp |
| Full-sample realised-mean static | No | 53.54% | +0.16 pp/yr | +1.01 pp |
| Fixed 60/40 policy | Yes | 60.00% | -0.25 pp/yr | +0.15 pp |

The excess CAGR falls monotonically as the comparator's own equity weight rises. A descriptive three-point regression gives a slope of about **-0.121 pp/year of excess CAGR for each +1 pp of comparator equity**, a fitted zero crossing near **56.70% equity**, and R² about **0.975**. The fitted edge at the dynamic strategy's own mean exposure is about **+0.38 pp/year**.

With only three dependent portfolio constructions, this is **descriptive geometry, not an independent inferential test**. It is nevertheless the pattern expected when most of the apparent return difference is equity beta/exposure and residual timing content is small. It would be an overstatement to say the regression proves that every basis point is beta.

The two decision-relevant sentences remain visible:

**Over the tested window, moving equity exposure added 0.16 pp/year of return and 1.0 pp of additional drawdown.**

**Against the pre-declared 60/40 policy over the same window, the dynamic model gave up about 0.25 pp/year of CAGR and took about 0.15 pp more maximum drawdown.**

## Strict timing-evidence gate

`scripts/robust_evaluation.py` continues to evaluate timing skill on the exposure-matched residual rather than total portfolio returns. Current diagnostics remain:

| Diagnostic | Result | Gate | Status |
| --- | ---: | ---: | --- |
| Exposure-matched timing edge | +0.16 pp/year | >0 | Positive but economically small |
| Circular-shift placebo percentile | 61.29% | ≥95% | Fail |
| AR(1) surrogate percentile | 62.78% | ≥95% | Fail |
| Deflated Sharpe probability on timing residual | 47.30% | ≥95% | Fail |
| CSCV/PBO on timing residual | 70.0% | ≤10% | Fail |
| Paired 3/6/12-month block-bootstrap lower bounds | Cross zero | >0 for all | Fail / inconclusive |

The 47.30% DSR figure is **not** a Bayesian posterior on the sign of the true Sharpe. It means the selected timing-residual Sharpe does not clear the selection-adjusted expected-maximum benchmark and supplies no positive evidence under that diagnostic.

The observed residual t-statistic is only about 0.17. Mechanical square-root-of-time scaling gives roughly 709 years to |t|=2 under IID assumptions and about 1,682 years if the observed effective-sample efficiency persisted. Those numbers are heuristic, nonstationary illustrations whose purpose is to show that “wait longer” is not an investment thesis for the current tiny point estimate.

The prospective ledger therefore exists to detect a **materially larger stable effect** if one emerges and to document its absence otherwise.

## SMA10 insurance: aggregate price and event payout

The frozen `trend-sma10-minus20-v1` rule remains live as an explicit policy-insurance choice. No -10 pp, -30 pp, continuous, dual-SMA or other trend alternatives are tested in this governance change.

Aggregate pricing remains:

| Window | CAGR premium paid | Max daily drawdown avoided | Underwater change |
| --- | ---: | ---: | ---: |
| Same 63 calendar return months | 0.09 pp/yr | 0.77 pp | +3 trading days |
| Longest exact shared history, 2011–Sep 2026 | 0.46 pp/yr | 1.37 pp | +38 trading days |

The longer-history 1.37 pp drawdown improvement remains below the frozen 5 pp automatic-promotion hurdle. The rule is therefore not reclassified as validated alpha.

The episode audit adds the question insurance actually needs to answer. Across the five largest non-overlapping baseline drawdowns, the brake's same-window drawdown payout was positive **5/5**. The largest recorded payouts included about +4.49 pp in the 2011 episode and about **+6.24 pp in the COVID episode**.

For COVID, the brake switched risk-off on **2 March 2020**, the NIFTY price trough in the audit occurred on **23 March 2020**, and the brake returned risk-on on **3 August 2020**. It therefore engaged **21 days before the trough**, not after it.

The trade-off appears on the rebound side: 12-month post-trough recovery return was lower for the braked strategy in **5/5** of the five largest episodes, with a median difference of about **-4.48 pp**. The most supportable description is therefore:

**The frozen SMA10 policy paid during the tested large drawdowns, including before/through the COVID trough, but systematically surrendered some recovery participation.**

That is a more informative insurance diagnosis than calling it simply “late” or “cheap.”

## Trial-count and parameter-search discipline

The exact DSR/PBO family remains the set of reproducible comparable strategies on the same objective, return definition and exact outcome matrix. Research versus production intent is not a statistical category.

The project does **not** search alternative trend magnitudes in this change. If -10, -30, continuous or other alternatives are later tested, every comparable attempt must enter the relevant selection family before any selected winner can be considered. The same rule applies to alternative macro budgets.

The present 24-member valuation-curve family remains unchanged because V3.5/V3.6 macro changes, the V3.10 P/B calibration regime, V3.11 trend insurance and V3.12 macro-shadow governance do not currently form additional certified columns on the exact same 63-month valuation-core outcome matrix. Any future reconstruction that does must increase the burden.

## Data integrity controls

The production pipeline preserves these controls:

- source failures are isolated rather than neutral-filled;
- stale, future-dated and undated required observations are rejected;
- individual observation dates are preserved rather than relabelled with refresh time;
- completed months are used for monthly trend/cycle calculations;
- duplicate periods and ambiguous multi-series responses are rejected;
- failed browser reads clear previously displayed allocations;
- the prospective evidence archive preserves first-seen observations and exact model versions;
- earnings and SMA10 remain fail-closed live inputs;
- macro remains fail-closed **for the shadow calculation**, but macro incompleteness cannot block or alter the V3.12 live target.

## Known limitations

- The live V3.12 stack lacks a certified historical release-vintage reconstruction through 2008 and March 2020.
- The clean current-methodology valuation sample is short and current references were not demonstrably frozen at its start.
- Valuation lenses are correlated rather than independent evidence.
- The 10 bps one-way transaction-cost convention is not an Indian after-tax implementation model.
- ETF/fund TER, tracking error, exit loads, tax lots and capital-gains taxes are not fully modelled.
- Monthly drawdowns can understate intramonth losses.
- SMA10 cannot protect against an overnight gap before the monthly signal can change.
- Zero live macro authority does not prove macro is useless; it means incremental authority has not yet earned its operational/evidence burden.
- No historical result makes the system crash-proof or guarantees outperformance.

## Multi-asset boundary

Gold and Silver remain separate research diversification sleeves carved from the core allocation; Bitcoin remains outside the retirement-core 100% by design. Their historical research is not an exact Indian after-tax implementation. See `MULTIASSET.md`.

## Verification and publication

The repository test suite covers source parsing, stale-data rejection, completed-month logic, drawdown accounting, turnover, evidence-ledger integrity, zero-live/shadow-only macro governance, the frozen SMA10 brake, timing-residual statistics, comparator geometry and episode attribution.

The normal refresh publishes the V3.12 packet, prospective `walkforward_v3_12.json`, benchmark audit and macro-authority audit. A separate governed insurance workflow publishes both aggregate SMA10 pricing and episode attribution.

The original V3.4 audit remains available in Git history. Its discovered STOXX binding and other data-integrity defects are historical evidence for why semantic source risk is treated explicitly today, not a claim that every current source is wrong.

For performance/evidence details see `ROBUSTNESS_AUDIT.md`; for machine-readable policy see `validation_policy.json` and the files under `data/`.
