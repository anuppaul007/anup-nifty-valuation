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

## What the audit measures

The script:

- classifies every monthly screen observation into its actual methodology era;
- reports era-specific medians, >80% equity/debt counts and saturation counts;
- fetches the published NIFTY 50 P/E, P/B and Dividend Yield on the trading day immediately before and after each official methodology break;
- holds the G-sec input constant and recomputes the frozen valuation formula to show how much the published ratio break can move the allocation;
- price-adjusts the changed ratios to separate ordinary one-day index movement from the observed ratio discontinuity as far as possible;
- runs descriptive return results separately inside each methodology era using the existing NIFTY TRI/conservative-debt/10-bps research assumptions;
- inventories which modern macro inputs have point-in-time/vintage support and which do not;
- samples the OECD India 10Y FRED/ALFRED series at historical vintage dates where available.

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

Likewise, the modern macro block mixes clean dated market observations with monthly or weekly macro releases whose original historical vintages have not all been reconstructed. Therefore:

- the 2000-present fixed-core valuation study remains **exploratory cross-methodology evidence**;
- the modern full-macro model does **not** currently have a 2000-present vintage-clean backtest;
- only prospective frozen evidence can be treated as fully untouched live evidence today.

No retrospective result from this audit can authorize a live-model parameter change.
