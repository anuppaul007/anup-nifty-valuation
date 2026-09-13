# Anup Nifty Valuation — V3.13

Automated NIFTY valuation and experimental equity/debt allocation.
[Open dashboard](https://anuppaul007.github.io/anup-nifty-valuation/).

**Investment timing advantage is not demonstrated. Independent validation is
not complete.** Read [the reliability review](RELIABILITY_REVIEW.md) for the
structural fixes, allocation impact, assumptions and open findings.

## Current live policy

- Four correlated valuation lenses: P/E, log profitability-adjusted P/B,
  earnings yield minus daily India government-bond yield, and dividend yield.
- Normalized weights: 31.58%, 26.32%, 31.58%, 10.53%. P/B-to-P/E is an
  index-implied profitability proxy, not independently measured ROE.
- Frozen curve k=1.35, zc=2.5. The valuation core can reach 0% or 100% equity.
- Earnings policy overlay up to ±6 percentage points; one-way SMA10 trend brake
  of 20 percentage points in risk-off months. Macro has zero live authority;
  verified macro context retains a ±6 pp prospective shadow challenger.
- These policy conventions have not been shown to maximize after-tax returns.

The P/B correction uses the same 36 month-end observations from September 2023
through August 2026, with a log form that removes the old low-P/E sign reversal.
It changes allocation prospectively and does not rewrite historical results.

## Reliability and interpretation

The live target requires matching model/data versions, a packet no older than
72 hours, NIFTY and a live daily bond yield no older than seven calendar days,
complete previous-month earnings evidence, and ten reconstructed consecutive
trend closes ending in the previous completed month. Monthly/cached yields
cannot substitute for current daily inputs. Missing inputs withhold the target.
These age limits are operating conventions, not service guarantees.

The page displays conditional reference index levels, fair-P/E sensitivity,
earnings sensitivity and an equity-crash loss illustration. None is a statistical
confidence interval or forecast. Education SGB and Bitcoin are outside the
retirement allocation; separately required spending is outside the investable sleeve.

NIFTY data come from NSE/Nifty Indices through jugaad-data. RBI/FBIL provide daily
yield proxies, which are not identical instruments. Public macro sources remain
context only. Original historical release vintages and complete constituent-level
fundamentals remain unverified. [Historical evidence](ROBUST_EVALUATION.md) applies
to its stated legacy experiment, not the new full live stack.

## Automation

The live refresh runs at 18:45 IST on weekdays, on code pushes and by manual
workflow dispatch. GitHub schedules may be delayed. Core refresh and structural
validation publish separately from optional historical/fund research. Browser
loading tries the deployed same-origin packet first, then public GitHub API/raw
fallbacks, always checking version and freshness. Reload fetches published data;
it does not trigger source-provider refresh.

Exact tested Python dependencies are pinned. The evidence archive includes
model, upstream pipeline, valuation modules and all policy definitions. Earlier
records are immutable; V3.13 prospective observations use their own ledger.

## Reproduce and review

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/*.test.cjs
python scripts/reliability_audit.py
```

[Independent review protocol](INDEPENDENT_REVIEW.md) describes the work still
needed from a reviewer who did not develop the model. Developer-authored tests
and AI criticism do not by themselves satisfy that requirement.
