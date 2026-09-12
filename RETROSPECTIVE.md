> Superseded calculations: see [V3.7 robustness audit](ROBUSTNESS_AUDIT.md) for corrected drawdown and drift-aware turnover costs. The original numerical tables below are retained as an audit trail. This was never a full macro backtest.

# Valuation-core retrospective sensitivity — 12 September 2026

## Questions tested

1. Does a gentler valuation-to-equity curve (`k`) improve historical risk/reward versus the live V3.6 slope `k = 1.35`?
2. Does the live extreme threshold `zc = 2.5` push the model toward 0%/100% equity too readily, and do wider thresholds (`3.0`, `3.5`, `4.0`) improve the trade-off?

This study isolates the **valuation core only**. Earnings and macro overlays are not used in the historical allocations.

## Method

- Comparable valuation regime: **April 2021 onward**, after the NSE Indices P/E methodology change. Pre-change P/E observations are not mixed into this test.
- 64 comparable completed months, ending **July 2026**.
- 63 next-month performance observations.
- Equity benchmark: **NIFTY 50 Total Return Index**.
- Debt benchmark: **NIFTY 10 Yr Benchmark G-Sec** total-return index.
- Signal timing: month-end valuation signal is applied only to the **following completed month's** return.
- Cost sensitivity for dynamic strategies: **10 bps per 100% one-way allocation turnover**. Taxes are excluded.
- The current fixed valuation reference constants remain unchanged in every candidate.

Important limitation: this is a **retrospective sensitivity study, not true out-of-sample validation**. The current fixed reference constants were not proven to have been frozen in April 2021. A historical grid winner therefore cannot be adopted automatically.

## A. Curve-slope test with the live extreme threshold `zc = 2.5`

Dynamic results use the 10-bp turnover-cost sensitivity.

| Curve slope `k` | CAGR | Annual vol. | Max drawdown | Calmar | Avg. equity | Min equity | Max equity |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.60 | 8.64% | 8.36% | -9.10% | 0.949 | 52.0% | 1.0% | 78.4% |
| 0.80 | 8.71% | 8.46% | -9.21% | 0.945 | 52.3% | 0.8% | 80.5% |
| 1.00 | 8.78% | 8.58% | -9.34% | 0.940 | 52.7% | 0.6% | 82.9% |
| 1.15 | 8.84% | 8.67% | -9.45% | 0.936 | 53.1% | 0.5% | 84.7% |
| **1.35 — live** | **8.93%** | **8.81%** | **-9.60%** | **0.930** | **53.5%** | **0.35%** | **87.0%** |
| 1.50 | 9.00% | 8.92% | -9.73% | 0.925 | 53.9% | 0.27% | 88.6% |

## B. Extreme-threshold test with the live slope `k = 1.35`

| Extreme threshold `zc` | CAGR | Annual vol. | Max drawdown | Calmar | Avg. equity | Min equity | Max equity |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **2.5 — live** | **8.93%** | 8.81% | -9.60% | 0.930 | 53.54% | **0.35%** | 87.01% |
| 3.0 | 8.92% | 8.76% | -9.55% | 0.933 | 53.42% | 1.99% | 85.78% |
| 3.5 | 8.91% | 8.73% | -9.53% | 0.935 | 53.36% | 2.80% | 85.18% |
| 4.0 | 8.91% | **8.72%** | **-9.52%** | **0.936** | 53.33% | **3.21%** | 84.87% |

Widening the endpoint from 2.5 to 4.0 therefore reduced turnover, volatility and drawdown modestly while sacrificing only about **0.02 percentage points of annualized return** in this sample. It also stopped the live slope from going quite as close to zero equity, although a 3.2% minimum equity allocation is still an extreme defensive position.

## C. Full `k × zc` grid

The full grid tests 24 combinations: six slopes × four extreme thresholds.

- **Highest net CAGR:** `k = 1.50`, `zc = 2.5` — approximately **9.00% CAGR**.
- **Highest net Calmar:** `k = 0.60`, `zc = 4.0` — approximately **8.63% CAGR**, **8.13% volatility**, **-8.87% max drawdown**, **0.972 Calmar**. Its allocation range in the sample was about **12.7% to 71.6% equity**.
- The high-Calmar grid winner is therefore much less extreme, but it also gives up return and behaves much more like a permanently balanced portfolio.

For context, fixed allocations over the same return window were:

| Fixed allocation | CAGR | Annual vol. | Max drawdown | Calmar |
| --- | ---: | ---: | ---: | ---: |
| **60% equity / 40% debt** | **9.18%** | 8.75% | -9.45% | **0.971** |
| 70% equity / 30% debt | 9.80% | 9.91% | -10.77% | 0.910 |
| 100% equity | 11.58% | 13.48% | -14.68% | 0.789 |

No tested dynamic combination beat fixed 60/40 on both return and Calmar. The best grid Calmar (0.972) was essentially the same as 60/40 (0.971), but its CAGR was lower (8.63% versus 9.18%). This is an important negative result: the current valuation-timing rule has **not** demonstrated superior risk-adjusted performance in this short common-methodology era.

## Effect on today's V3.6 signal

For the current September 2026 signal (`valuation z ≈ -1.052`), keeping the live slope `k = 1.35` and all earnings/macro inputs unchanged gives these candidate final targets:

| `zc` | Candidate final equity target |
| ---: | ---: |
| **2.5 — live** | **81.55%** |
| 3.0 | 80.47% |
| 3.5 | 79.93% |
| 4.0 | 79.66% |

So widening the extreme threshold alone **does not solve the current 81% concern**. Even `zc = 4.0` lowers today's target by only about **1.9 percentage points**. The present high target is driven mainly by the valuation composite itself and the chosen mapping of moderately cheap valuation into strategic equity, not by one single endpoint parameter.

## Decision for V3.6

**Do not change either live parameter (`k = 1.35`, `zc = 2.5`) from this retrospective evidence.** The prospective walk-forward lock remains active.

The prospective ledger now records all four endpoint candidates (`2.5`, `3.0`, `3.5`, `4.0`) and the full slope × threshold grid every month. The parameter gate requires a long enough genuinely forward sample before any live change can be considered.

## Interpretation

The endpoint test gives a useful directional signal: **wider extreme thresholds are somewhat more stable and less prone to near-zero equity allocations, but the improvement is modest and the sample is too short to establish superiority.** More importantly, neither slope nor endpoint tuning has justified a retrospective rewrite of the live model.

The next research question should therefore move one level higher: test whether the **fixed valuation references and lens weights themselves** are robust under rolling / expanding-window calibration, rather than continuing to optimize the shape of the allocation curve after observing outcomes.

The machine-readable results are stored in [`data/retrospective.json`](data/retrospective.json), and the prospective ledger is stored in [`data/walkforward.json`](data/walkforward.json).
