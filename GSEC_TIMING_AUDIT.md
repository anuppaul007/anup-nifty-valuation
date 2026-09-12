# Historical 10-year G-sec timing audit

Status: **research only**. This does not change the live V3.6 allocator, `model.js`, `multiasset.py`, or any prospective archived decision.

## Problem being tested

The V3.9 historical evidence screen currently applies a blanket two-calendar-month lag to the 10-year government-yield input. That is deliberately conservative, but it is not the best point-in-time convention for RBI's archived **month-end SGL transaction-yield** observations.

For a month-start allocation decision made after the previous trading day's close and before the first trading session of the new month, the immediately preceding RBI month-end market observation was already observable. Therefore the research challenger uses the latest RBI SGL month-end observation strictly before the signal date.

OECD monthly long-term yields are treated differently. Their historical publication timing and release vintages have not been verified, so the point-in-time-safe challenger **does not advance OECD rows**. A separate `observation_date_only` sensitivity advances all stored observations by observation date, but it is explicitly not claimed to be vintage-safe.

## Official RBI basis

RBI handbooks label the relevant table **“Month-end Yield of SGL Transactions in Government Dated Securities for Various Maturities.”** The 10-year row is therefore a market observation at month-end, not a macro statistic whose observation month should automatically be delayed by two calendar months.

Reference examples used for the audit definition:

- RBI Handbook 2015-16, Table 187: `https://www.rbi.org.in/scripts/PublicationsView.aspx?id=17320`
- RBI Handbook 2023-24, Table 180: `https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=22654`

The current historical screen already stores the archived RBI month-end observations and their source URLs. The audit re-aligns those stored observations rather than inventing or interpolating yields.

## Variants

1. **incumbent** — current V3.9 timing exactly as stored.
2. **rbi_timing_corrected** — latest archived RBI month-end observation strictly before signal date; OECD rows unchanged.
3. **observation_date_only** — latest stored RBI/OECD observation strictly before signal date; sensitivity bound only, not a point-in-time-safe OECD reconstruction.

All variants recompute the same frozen V3.6 valuation-core formula and allocation curve. The script verifies that recomputing the incumbent reproduces the stored z-score and core-equity allocation to machine precision.

## Economic sensitivity

The CI job also applies each target series to the existing exploratory protocol return panel using NIFTY 50 TRI, the conservative debt proxy, a zero rebalance band, and 10 bps one-way turnover cost. This is only to measure whether the timing convention is economically material.

It is **not** a historical full-macro/earnings validation, does not cure the pre-2021 NIFTY valuation-methodology comparability issue, and cannot authorize a live-model parameter change.
