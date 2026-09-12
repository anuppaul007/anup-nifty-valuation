# Valuation-core retrospective sensitivity — 12 September 2026

## Question tested

Does a gentler valuation-to-equity curve (roughly `k = 0.8–1.0`) give a better historical risk/reward result than the live V3.6 curve (`k = 1.35`)?

This study isolates the **valuation core only**. It does not use the earnings or macro overlays when generating historical allocations.

## Method

- Comparable valuation regime: **April 2021 onward**, after the NSE Indices P/E methodology change. Pre-change P/E observations are not mixed into this test.
- 64 comparable completed months, ending **July 2026**.
- 63 next-month performance observations.
- Equity benchmark: **NIFTY 50 Total Return Index**.
- Debt benchmark: **NIFTY 10 Yr Benchmark G-Sec**, which is a total-return fixed-income index (not the clean-price version).
- Signal timing: month-end valuation signal is applied only to the **following completed month's** return.
- Cost sensitivity for dynamic strategies: **10 bps per 100% one-way allocation turnover**. Taxes are excluded.
- All candidate curves retain the same current fixed valuation references and the same `zc = 2.5` 0%/100% endpoint threshold.

Important limitation: this is a **retrospective sensitivity study, not true out-of-sample validation**. The current fixed reference constants have not been shown to have been frozen in April 2021. Results therefore must not be used to optimize the live model after seeing the outcome.

## Results

Dynamic results below use the 10-bp turnover-cost sensitivity.

| Curve slope `k` | CAGR | Annual vol. | Max drawdown | Calmar | Avg. equity | Min equity | Max equity |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.60 | 8.64% | 8.36% | -9.10% | 0.949 | 52.0% | 1.0% | 78.4% |
| 0.80 | 8.71% | 8.46% | -9.21% | 0.945 | 52.3% | 0.8% | 80.5% |
| 1.00 | 8.78% | 8.58% | -9.34% | 0.940 | 52.7% | 0.6% | 82.9% |
| 1.15 | 8.84% | 8.67% | -9.45% | 0.936 | 53.1% | 0.5% | 84.7% |
| **1.35 — live** | **8.93%** | **8.81%** | **-9.60%** | **0.930** | **53.5%** | **0.35%** | **87.0%** |
| 1.50 | 9.00% | 8.92% | -9.73% | 0.925 | 53.9% | 0.27% | 88.6% |

For context, fixed allocations over the same return window were:

| Fixed allocation | CAGR | Annual vol. | Max drawdown | Calmar |
| --- | ---: | ---: | ---: | ---: |
| 60% equity / 40% debt | 9.18% | 8.75% | -9.45% | 0.971 |
| 70% equity / 30% debt | 9.80% | 9.91% | -10.77% | 0.910 |
| 100% equity | 11.58% | 13.48% | -14.68% | 0.789 |

## What the study says

1. **The original suspicion that `k = 0.8–1.0` would clearly improve the model is not supported by this sample.** Gentler curves reduced volatility and drawdown slightly, but they also reduced return. Within the dynamic candidates, the highest net CAGR occurred at `k = 1.50`, while the best Calmar occurred at `k = 0.60`.

2. **No tested dynamic slope beat fixed 60/40 on both return and Calmar.** This is an important negative result. The valuation timing rule has not demonstrated superior risk-adjusted performance in the common post-2021 methodology era.

3. **The live `k = 1.35` curve is not uniquely responsible for the aggressive de-risking.** All tested slopes share `zc = 2.5`. In April 2021 the valuation z-score was about +2.43, very close to that endpoint, so every curve pushed equity close to zero. The live curve reached a minimum equity allocation of about 0.35% during this study. Changing slope alone cannot solve that endpoint behavior.

4. **The more important parameter to challenge next is the definition of “extreme”.** The current `zc = 2.5` means 0% equity at +2.5 and 100% equity at -2.5. The retrospective result suggests that this may move the model to an extreme allocation too early, but the 2021–2026 sample is too short to justify changing it after the fact.

5. **The strategy did reduce risk versus 100% equity.** The live valuation core had roughly 8.8% annualized volatility and a -9.6% maximum drawdown versus 13.5% volatility and a -14.7% maximum drawdown for 100% equity. The cost was materially lower CAGR in this particular period.

## Decision for V3.6

**Do not change the live curve slope from 1.35 based on this retrospective study.** The prospective walk-forward lock remains in force. The result is evidence against casually tuning the model to make today's allocation look more comfortable.

The current live target should therefore continue to be described as a **model-implied allocation**, not a historically proven return-maximizing target.

## Next research step

The next sensitivity test should vary the endpoint threshold separately from the slope, for example `zc = 2.5, 3.0, 3.5, 4.0`, while keeping the same no-lookahead monthly return convention. That test should answer whether the model reaches 0%/100% equity too easily. Any candidate settings should then be recorded prospectively rather than automatically adopted from the retrospective winner.

The machine-readable results are stored in [`data/retrospective.json`](data/retrospective.json), and the live prospective ledger remains in [`data/walkforward.json`](data/walkforward.json).
