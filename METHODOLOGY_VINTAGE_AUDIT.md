# NIFTY methodology and release-vintage audit

Status: **research only**. This work does not change the live V3.6 allocator, `model.js`, `multiasset.py`, or any prospective archived decision.

## Why this audit exists

The published NIFTY 50 valuation history is not a single like-for-like time series under today's definitions.

Official NSE Indices changes:

1. **31 March 2021** — P/E changed from trailing-four-quarter **standalone** earnings to trailing-four-quarter **consolidated** earnings, with standalone fallback where consolidated financials are unavailable. Dividend Yield also changed from annual-report dividend amounts to **rolling 12-month equity dividends based on ex-dividend date**.
2. **29 September 2023** — P/B changed from annual-report **standalone** net worth to **consolidated** net worth, again with standalone fallback where consolidated financials are unavailable.

Official sources:

- NSE Indices press release dated 23-Feb-2021: `https://www.niftyindices.com/Press_Release/ind_prs23022021_1.pdf`
- NSE Indices press release dated 17-Aug-2023: `https://www.niftyindices.com/Press_Release/ind_prs17082023.pdf`
- Current P/E definition: `https://www.niftyindices.com/resources/index-concepts/price-earnings-ratio`
- Current P/B definition: `https://www.niftyindices.com/resources/index-concepts/price-to-book-value`
- Current Dividend Yield definition: `https://www.niftyindices.com/resources/index-concepts/dividend-yield`

## Three methodology eras

The audit therefore treats the history as three regimes:

- **Era A — before 31-Mar-2021:** standalone P/E, standalone P/B, old annual-report dividend-yield basis.
- **Era B — 31-Mar-2021 to 28-Sep-2023:** consolidated P/E and rolling-12m dividend yield, but standalone P/B.
- **Era C — 29-Sep-2023 onward:** consolidated P/E, consolidated P/B and rolling-12m dividend yield — the only era in which all three published valuation ratios use today's definitions.

This matters because V3.6 fixed reference constants are modern-model constants. Applying them unchanged to older published ratio definitions is an exploratory sensitivity, not an apples-to-apples current-definition backtest.

## Audit result

The 321-month screen splits into **255 legacy-definition months**, **30 mixed-definition months**, and only **36 fully current-definition months**.

| Era | Months | Valuation strategy CAGR* | NIFTY 50 TRI CAGR | Strategy max monthly drawdown | NIFTY max monthly drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| A — legacy definitions | 255 | 16.74% | 12.63% | -34.20% | -55.94% |
| B — current P/E & DY, legacy P/B | 30 | 9.17% | 12.93% | -6.02% | -11.37% |
| C — fully current definitions | 36 | 8.55% | 7.46% | -8.02% | -13.92% |

\*Exploratory implementation assumptions: stored historical yield convention, NIFTY 50 TRI, conservative debt proxy, zero rebalance band and 10 bps one-way turnover cost. Era B and especially Era C are too short to constitute validation samples.

This is the key interpretation change: the very strong 2000-present historical return advantage is dominated by **Era A**, whose P/E, P/B and dividend-yield definitions are not the same as today's. The fully current-definition Era C has so far produced a modest return advantage with materially lower drawdown, but **36 months is nowhere near enough to prove the exact current model**.

### Published break observations

At the 31-Mar-2021 P/E/dividend-yield methodology change, the published P/E fell from **40.43 to 33.20** while NIFTY itself fell about **1.04%**. After removing that one-day price move mechanically, the P/E ratio change is still very large (price-adjusted factor about **0.83**). The frozen valuation z-score moves from about **4.11 to 2.64**. The allocation remains **0% equity in both cases only because the allocation curve is already saturated at the extreme-overvaluation endpoint**. A zero percentage-point allocation jump therefore does **not** mean the methodology change was economically irrelevant.

At the 29-Sep-2023 P/B methodology change, published P/B fell from **4.31 to 3.46** while NIFTY rose about **0.59%**. The price-adjusted P/B factor is about **0.80**. Holding the G-sec input constant, the frozen valuation allocation moves from about **51.5% equity to 56.0% equity**, a **+4.52 percentage-point** jump.

These adjacent published observations quantify the discontinuity seen by the model but do not identify a pure accounting-methodology bridge. Both dates coincide with live market movement and index maintenance/reconstitution.

## What the audit measures

The script:

- classifies every monthly screen observation into its actual methodology era;
- reports era-specific medians, >80% equity/debt counts and saturation counts;
- fetches the published NIFTY 50 P/E, P/B and Dividend Yield immediately before and after each official methodology break;
- holds the G-sec input constant and recomputes the frozen valuation formula to show how much the published ratio break can move allocation;
- price-adjusts changed ratios to separate ordinary one-day index movement from the observed discontinuity as far as possible;
- runs descriptive return results separately inside each methodology era;
- inventories which modern macro inputs have point-in-time/vintage support and which do not;
- attempts an automated OECD India 10Y FRED/ALFRED vintage sample where network access permits.

## What the audit deliberately does **not** do

It does **not** splice or rescale the pre-change ratios to today's definitions from a one-day jump. Both official methodology changes coincide with index maintenance/reconstitution and live market movement, and there is no simultaneous old/new-definition history. Any such bridge would be an assumption presented as data.

A truly apples-to-apples 2000-present current-definition reconstruction would require constituent-level historical:

- consolidated trailing-four-quarter earnings;
- consolidated annual-report net worth;
- rolling-12-month dividends by ex-dividend date;
- historical NIFTY membership, shares and investible-weight factors as they existed at each decision date.

That is a much larger accounting-data reconstruction project and should be treated separately from the official published-ratio history.

## Release-vintage boundary

The OECD India 10-year government-bond series (`INDIRLTLT01STM`) starts in Dec-2011, while ALFRED exposes revision/vintage history from its later FRED/ALFRED availability period (visible from 17-Jul-2018). That is useful for testing later vintages, but it does **not** prove the original release path for 2011-2018.

The CI run's automated FRED vintage download timed out, so its machine sampler reports `unavailable`. That status means **the automated network sample was unavailable in that run**, not that ALFRED lacks a vintage archive. The audit therefore relies on the documented archive boundary rather than pretending a failed network request is evidence about data availability.

Likewise, the modern macro block mixes clean dated market observations with monthly or weekly macro releases whose original historical vintages have not all been reconstructed. Therefore:

- the 2000-present fixed-core valuation study is **useful exploratory cross-methodology evidence**, not a clean backtest of today's exact ratio definitions;
- the modern full-macro model does **not** currently have a 2000-present vintage-clean backtest;
- the exact current ratio-definition history begins only on **29-Sep-2023**;
- only prospective frozen evidence can be treated as fully untouched live evidence today.

No retrospective result from this audit can authorize a live-model parameter change.
