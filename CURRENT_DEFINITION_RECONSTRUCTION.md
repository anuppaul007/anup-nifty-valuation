# Current-definition NIFTY 50 reconstruction

Status: **research only**. This work does not change the live V3.6 allocator, `model.js`, `multiasset.py`, `latest.json`, or any prospective archived decision.

## Research question

The earlier methodology audit showed that the published NIFTY valuation history is not homogeneous. This project asks a narrower, harder question:

> What would the NIFTY 50 P/E, P/B and dividend yield have been historically if the **current accounting definitions** had been applied using only information public at each decision date?

The reconstruction keeps the **actual historical NIFTY weights that existed at each date**. It does **not** pretend that today's free-float weighting existed before NIFTY actually adopted free-float methodology. That avoids mixing the accounting-definition question with a second weighting counterfactual.

## Key source breakthrough: official weights exist far earlier than 2008

The weight-history problem is more tractable than initially expected. NSE's *Indian Securities Market — A Review 2001* contains **Annexure 4.2: Weightage of S&P CNX Nifty Securities: April 2000–June 2001**, with one weight for each constituent in each month and markers for the month a security entered the index. The source is IISL/NSE.

Official source:

- `https://nsearchives.nseindia.com/web/sites/default/files/inline-files/ismr.pdf`

Subsequent NSE market-review volumes continue the same type of monthly weightage annexures. For later years, the Nifty Indices Monthly Reports archive publishes **Indices Market Capitalisation & Weightage** ZIP files.

This matters because if the actual historical constituent weight `w_i` is known, a separate historical IWF does not need to be reconstructed merely to aggregate valuation ratios. The historical index weight already embeds whatever weighting/IWF/capping regime was actually in force.

## Exact aggregation algebra

For each constituent `i`, using values known by the signal date:

- `PE_i = market capitalisation_i / TTM earnings_i`
- `PB_i = market capitalisation_i / book value_i`
- `DY_i = rolling-12-month equity dividends_i / market capitalisation_i`

Then, using actual index weights that sum to one:

- `PE_index = 1 / Σ(w_i / PE_i)`
- `PB_index = 1 / Σ(w_i / PB_i)`
- `DY_index = Σ(w_i × DY_i)`

The reconstruction engine implements these identities directly and rejects materially incomplete weight snapshots.

## Today's accounting target

The target follows current Nifty Indices definitions:

- **P/E** — trailing-four-quarter **consolidated** earnings where available; standalone fallback only when consolidated financials are unavailable.
- **P/B** — **consolidated** net worth from the latest eligible annual financials where available; standalone fallback only when consolidated financials are unavailable.
- **Dividend Yield** — rolling twelve-month equity dividends using **ex-dividend dates**.

A filing/result/action is eligible only if it was public no later than the model signal timestamp. Later filings cannot be pulled backward into earlier months.

## Sources to be used

Authoritative/public source families:

1. **Historical constituent weights** — NSE/IISL annual market-review annexures from April 2000; later Nifty Indices monthly market-capitalisation/weightage archives.
2. **Financial results** — NSE corporate filings and XBRL/iXBRL records where available.
3. **Dividends and capital actions** — NSE corporate actions, using ex-dates and explicit split/bonus continuity.
4. **Prices / market-cap basis** — NSE market history, aligned with the accounting numerator and corporate-action state.

An independent open-source NSE membership reconstruction may be used as a **cross-check only**. It is not a source of record.

## Strict reconstructability gate

A month is not promoted to `reconstructable` unless all 50 constituents have:

- exact official constituent membership and index weights;
- point-in-time eligible TTM consolidated earnings, or documented standalone fallback;
- point-in-time eligible consolidated book value, or documented standalone fallback;
- complete rolling-12-month dividend history by ex-date;
- a consistent market-capitalisation / price-share basis;
- corporate-action continuity;
- no missing valuation field.

There is **no neutral fill, interpolation, cross-sectional imputation, methodology-jump scaling or look-ahead**. A month with 49 complete companies is an incomplete month.

## What Phase 1 implements

`scripts/current_definition_reconstruction.py` now provides:

- deterministic constituent-to-index PE/PB/DY aggregation;
- strict weight-completeness checks;
- point-in-time filing eligibility checks;
- a 50/50 month-completeness gate;
- public-source probes for representative Nifty Indices weight archives;
- public-source probes for NSE financial results and corporate actions across a diverse set of large constituents;
- an explicit coverage report rather than an invented historical series.

The generated JSON intentionally leaves `earliest_fully_reconstructed_month = null` until a full 50-company month has actually passed the gate.

## Validation order

The safest validation sequence is:

1. **Recent pilot: Sep-2023 onward.** Reconstruct current-definition ratios from constituents and compare them with published NIFTY 50 P/E/P/B/DY, because both sides use the same definitions.
2. Declare the acceptable reproduction tolerance before extending the result backward.
3. Expand backward only across months with complete point-in-time company data.
4. Separately ingest the old NSE/IISL monthly weight tables back to Apr-2000.
5. Never label the remaining pre-coverage period as reconstructed unless its company-level accounting evidence is actually complete.

## Expected bottleneck

The key conceptual blocker is **no longer historical index membership/weights**: official NSE publications establish monthly weights from April 2000.

The harder blocker is historical company accounting data under today's definitions, especially before modern electronic/XBRL filing coverage. Old consolidated earnings, consolidated net worth, dividend actions, share counts and corporate actions must be assembled with their original availability dates. If public records are incomplete for a period, the correct result is a documented gap—not a synthetic backfill.

## Evidence interpretation

A successful reconstruction would materially strengthen the 2000-present valuation evidence. Until then:

- the existing long-history model remains useful **cross-methodology evidence**;
- the exact current-definition history remains proven only over the modern published regime;
- prospective frozen V3.6 evidence remains the cleanest untouched evidence for the full current model.

No retrospective result from this project can automatically authorize a live-model parameter change.
