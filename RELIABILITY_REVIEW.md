# V3.13 reliability review and release decision

Prepared 13 September 2026. Scope: prospective valuation and allocation reliability.
Status: experimental; independent investment validation remains incomplete.

The owner authorized improvements to the model and publication. This release
repairs identifiable mathematical and operational defects. It is **not** a
performance-gate pass, an optimized allocation, or a claim of institutional certification.
The historical timing gate still controls investment-performance claims.

## Findings and changes

| Finding | Consequence | V3.13 treatment |
|---|---|---|
| Subtractive profitability adjustment reverses the P/B sign at sufficiently low P/E | Increasing P/B can incorrectly lower the expensiveness score | Replace with a monotone log adjustment on the same frozen 36-month sample |
| Trend accepted a reported average without the ten underlying rows | Missing months, partial months or an altered average could pass | Publish and reconstruct all ten dated consecutive closes, ending in the previous completed month |
| Yield packet supplied its own permitted age and allowed lagged/cache status | A monthly average could drive a purportedly current daily target | Require live daily yield status and a code-owned seven-calendar-day limit; fallback remains visible but cannot publish a target |
| Model and data version were not required to agree | A cached page could calculate a new packet under older rules | Require exact engine/packet version; synchronize static copy and asset URLs |
| Browser timer checked wrapper age only | An individual input could expire while the old target stayed visible | Re-evaluate every required input each minute |
| Optional historical/fund research shared the live publication job | Unrelated research failure could block current inputs | Separate optional research publication from the live refresh |
| Floating dependency minimums and incomplete policy archive | Re-running later could use different dependencies or omit policy definitions | Pin tested direct/transitive Python versions; archive all policy files and valuation modules |
| Static page, README and live code disagreed about macro authority | Users without current JavaScript saw obsolete policy claims | Make V3.13 source and static disclosure consistent; remove the dated hard-coded allocation fallback |
| A precise target hid reference dependence | Users could mistake a convention for identified intrinsic value | Show conditional reference index levels, fair-P/E sensitivity, earnings sensitivity and portfolio-loss illustration |

## Why the old P/B formula was defective

With `q = 100 × PB / PE`, the former lens was

`zPB = (PB − pbM)/pbS − beta × (q − roeM)/roeS`.

Holding P/E fixed, its derivative with respect to P/B was

`1/pbS − 100 × beta/(PE × roeS)`.

It becomes negative below P/E approximately 19.67 with the frozen constants.
Thus a higher price-to-book ratio could look cheaper at precisely the low-P/E
levels this tool is intended to assess. The new form is

`u = ln(PB/pbM) − beta × ln(q/roeM)`

`zPB = (u − median(u_history)) / population_std(u_history)`.

The same September 2023–August 2026 rows and beta 0.60 are retained. The log
offset is 0.0031695843111495; scale is 0.062405429030436874. Neither was selected
against investment returns. Analytical derivatives are positive:

`∂zPB/∂PB = (1−beta)/(PB × scale)` and
`∂zPB/∂PE = beta/(PE × scale)`.

This fixes directional consistency. It does **not** establish that beta, weights,
reference levels or the resulting target are optimal. In particular, the P/B
adjustment still shares earnings information with the other valuation lenses.
The short calibration and correlated inputs remain limitations.

## Allocation policy and change control

The valuation curve retains k=1.35 and zc=2.5, including 0% and 100% core-equity
endpoints. Earnings remains a bounded ±6 percentage-point policy overlay.
The frozen SMA10 policy brake remains one-way at 0/−20 percentage points.
Macro remains zero live authority, with a verified ±6 pp shadow challenger.
The P/B repair can change the target materially; the same-input comparison is
published in `data/reliability_audit.json`. It must not be presented as a return gain.

This is an explicitly documented structural correction under the owner's
authorization, not an exception that turns failed performance tests into passes.
V3.13 is recorded as a separate hypothesis in the trial registry. If evaluated on
a comparable return matrix, it must join that matrix's multiple-testing family.
Older archived packets, monthly decisions and backtests are preserved. A new
version-specific prospective ledger starts without fabricated history.

## Interpreting the new valuation display

The reference levels solve for composite z = −0.674, 0 and +0.674 by moving price
and all price-dependent ratios together. Index-implied EPS, book value, dividends
and bond yield stay constant. These are **conditional model reference levels**,
not a fair-value confidence interval, price target or expected trading range.

The P/E sensitivity uses assumed references 18, 22.44 and 26, with all other
references and policy controls fixed. The earnings sensitivity changes earnings
at fixed price and book value while holding the earnings overlay and trend regime
constant to isolate the valuation effect. Scenarios carry no assigned probability.

Any allocation applies to the investable equity/debt sleeve after separately
reserving required near-term spending. Education SGB and Bitcoin remain outside
the retirement allocation. Debt is not automatically risk-free: instrument
duration, credit exposure, fees and taxes require separate implementation choices.

## Reproduction

Use Python 3.12 and Node 22 or later:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/*.test.cjs
python scripts/reliability_audit.py
```

The audit reproduces calibration in Python, checks a broad monotonicity grid,
calls the production JavaScript engine, and hashes inputs, model and policies.
Its evaluation clock is the packet's capture time; present-day eligibility is
checked separately by the browser and watchdog. These are developer tests, not
an independent model-risk opinion.

## What remains unresolved

1. Certified historical release vintages for the full stack and methodology-consistent constituent fundamentals.
2. An independently reproduced valuation assessment and evaluator review.
3. A demonstrated timing advantage over investable fixed-allocation benchmarks after costs and taxes.
4. Sufficient prospective history across market regimes, including drawdown and retirement-withdrawal outcomes.
5. Reliable source service guarantees. Public feeds can still fail; withholding a target is a valid operational outcome.

No rating or "institutional-grade" label substitutes for these findings. See
[the independent review protocol](INDEPENDENT_REVIEW.md) and the existing
[robust evaluation policy](robust_evaluation_policy.json).
