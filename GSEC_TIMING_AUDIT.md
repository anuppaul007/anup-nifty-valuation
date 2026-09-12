# Historical 10-year G-sec timing audit

Status: **research only**. This does not change the live V3.6 allocator, `model.js`, `multiasset.py`, or any prospective archived decision.

## Problem being tested

The V3.9 historical evidence screen currently applies a blanket two-calendar-month lag to the 10-year government-yield input. That is deliberately conservative, but it is unnecessarily stale for RBI's archived **month-end SGL transaction-yield** observations if the historical strategy is allowed to use the market yield observed at the previous month-end.

For a month-start allocation decision made after the previous trading day's close and before the first trading session of the new month, the immediately preceding RBI month-end yield is the economically contemporaneous market observation. The research challenger therefore uses the latest RBI SGL month-end observation strictly before the signal date.

This is an explicit **market-observation availability assumption**, not a claim that the later RBI Handbook table itself was published on that month-end date. The archive establishes the observation date and value; the historical publication timestamp of each archived table entry has not been independently verified. This distinction is why the work remains research evidence rather than a live-model promotion.

OECD monthly long-term yields are treated more conservatively. Their historical publication timing and release vintages have not been verified, so the RBI-only challenger **does not advance OECD rows**. A separate `observation_date_only` sensitivity advances all stored observations by observation date, but it is explicitly not claimed to be vintage-safe.

## Official RBI basis

RBI handbooks label the relevant table **“Month-end Yield of SGL Transactions in Government Dated Securities for Various Maturities.”** The 10-year row is therefore a month-end secondary-market observation, not a macro statistic whose observation month itself should automatically be interpreted as two months old.

Reference examples used for the audit definition:

- RBI Handbook 2015-16, Table 187: `https://www.rbi.org.in/scripts/PublicationsView.aspx?id=17320`
- RBI Handbook 2023-24, Table 180: `https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=22654`

The current historical screen already stores the archived RBI month-end observations and their source URLs. The audit re-aligns those stored observations rather than inventing or interpolating yields.

## Variants

1. **incumbent** — current V3.9 timing exactly as stored.
2. **rbi_timing_corrected** — latest archived RBI month-end market observation strictly before signal date; OECD rows unchanged. This uses the explicit market-observation availability assumption above.
3. **observation_date_only** — latest stored RBI/OECD observation strictly before signal date; sensitivity bound only, not a point-in-time-safe OECD reconstruction.

All variants recompute the same frozen V3.6 valuation-core formula and allocation curve. The script verifies that recomputing the incumbent reproduces the stored z-score and core-equity allocation to machine precision.

## Audit result

Across 321 monthly signals, the RBI timing correction changes the selected yield month in 144 observations. Mean absolute allocation movement is only **0.66 percentage point**, the maximum movement is **9.90 percentage points**, and only **5 months** cross the strict >80% equity / >80% debt classification boundary.

Using the same exploratory implementation assumptions as the protocol study (NIFTY 50 TRI, conservative debt proxy, zero rebalance band and 10 bps one-way turnover cost), CAGR changes from **15.07%** under the stale incumbent timing to **14.99%** under the RBI timing correction. Maximum monthly drawdown changes from **-34.20%** to **-34.70%**. The all-observation-date sensitivity is almost identical at **14.99% CAGR**.

The result therefore says the two-month RBI lag is a real historical-timing weakness worth correcting in research, but it is **not the source of the strategy's long-run return advantage**.

## Limits

This is **not** a historical full-macro/earnings validation. It does not cure the pre-2021 NIFTY valuation-methodology comparability issue, does not establish historical OECD release vintages, and does not establish the exact publication time of every RBI archived table entry. The economic backtest uses monthly rather than the validation policy's primary daily-drawdown metric. It cannot authorize a live-model parameter or allocation change.
