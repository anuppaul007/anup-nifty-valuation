# Current-definition NIFTY 50 reconstruction

Status: **research only**. This work does not change the live V3.13 allocator, `model.js`, `multiasset.py`, `latest.json`, or any prospective archived decision.

> **Aggregation correction (13 Sep 2026):** the original Phase-1 positive-constituent P/E/P/B helper is superseded for future reconstruction by `scripts/current_definition_aggregation.py` and `current_definition_aggregation_policy.json`. Current Nifty P/E aggregates constituent **profits and losses**; a loss-making constituent cannot be discarded merely because its individual P/E is negative or undefined. See `CURRENT_DEFINITION_ALGEBRA_CORRECTION.md`.

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

## Controlling aggregation algebra

For constituent `i`, using only values public by the signal date:

- `w_i` = actual published historical index weight;
- `M_i` = company market capitalisation on a basis consistent with the financial numerator;
- `E_i` = TTM earnings, **signed**;
- `B_i` = eligible annual net worth/book value, **signed if reported**;
- `D_i` = rolling-12-month eligible equity dividends by ex-date.

Then:

- `index earnings yield = Σ(w_i × E_i / M_i)`
- `index book yield = Σ(w_i × B_i / M_i)`
- `index dividend yield = Σ(w_i × D_i / M_i)`

and therefore:

- `PE_index = 1 / index earnings yield` **only while aggregate index earnings are positive**;
- `PB_index = 1 / index book yield` when the aggregate denominator is non-zero;
- `DY_index = 100 × index dividend yield`.

This is the controlling form for future reconstruction because it handles zero earnings and preserves negative earnings/net-worth contributions. The simpler harmonic-ratio identities are only a special positive-denominator case.

The published historical weight is sufficient for this aggregation when the company market-cap basis is matched correctly: the unknown free-float/IWF/capping factor embedded in `w_i` cancels into `w_i × E_i/M_i`, and likewise for book value and dividends.

## Today's accounting target

The target follows current Nifty Indices definitions:

- **P/E** — trailing-four-quarter **consolidated** earnings where available; standalone fallback only when consolidated financials are unavailable; profits and losses are aggregated. If overall index earnings are negative, Nifty Indices does not publish P/E until aggregate earnings become positive again.
- **P/B** — **consolidated** net worth from the latest eligible annual financials where available; standalone fallback only when consolidated financials are unavailable; aggregation is based on gross adjusted book value/net worth.
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
- a consistent company market-capitalisation basis;
- point-in-time eligible TTM consolidated earnings, or documented standalone fallback, **including zero/negative earnings rather than dropping them**;
- point-in-time eligible consolidated net worth/book value, or documented standalone fallback;
- complete rolling-12-month dividend history by ex-date;
- corporate-action continuity;
- no missing company numerator.

There is **no neutral fill, interpolation, cross-sectional imputation, methodology-jump scaling, loss-maker exclusion or look-ahead**. A month with 49 complete companies is an incomplete month.

## What Phase 1 implements

`scripts/current_definition_reconstruction.py` provides the original feasibility/source probes, weight-completeness checks, point-in-time eligibility primitives and explicit coverage report. Its original positive-constituent harmonic-ratio helper is retained as historical Phase-1 code but is **not controlling for future certification**.

`scripts/current_definition_aggregation.py` now provides the controlling signed-denominator aggregation and strict company-numerator gate for future constituent reconstruction. CI explicitly tests loss-making constituents, zero earnings and negative book-value contributions.

The generated feasibility JSON intentionally leaves `earliest_fully_reconstructed_month = null` until a full 50-company month has actually passed the modern gate.

## Validation order

The safest validation sequence is:

1. **Recent pilot: Sep-2023 onward.** Reconstruct current-definition ratios from all constituent numerators and actual weights and compare them with published NIFTY 50 P/E/P/B/DY, because both sides use the same definitions.
2. Declare the acceptable reproduction tolerance **before** extending the result backward.
3. Expand backward only across months with complete point-in-time company data.
4. Separately ingest the old NSE/IISL monthly weight tables back to Apr-2000.
5. Never label the remaining pre-coverage period as reconstructed unless its company-level accounting evidence is actually complete.

## Expected bottleneck

The key conceptual blocker is **no longer historical index membership/weights**: official NSE publications establish monthly weights from April 2000.

The harder blocker is historical company accounting data under today's definitions, especially before modern electronic/XBRL filing coverage. Old consolidated earnings, consolidated net worth, dividend actions, share counts and corporate actions must be assembled with their original availability dates. If public records are incomplete for a period, the correct result is a documented gap—not a synthetic backfill.

## Evidence interpretation

A successful reconstruction would materially strengthen the 2000-present valuation evidence. Until then:

- the existing long-history model remains useful **cross-methodology evidence**;
- exact current-definition history remains proven only over the modern published regime;
- the prospective frozen evidence ledger remains the cleanest untouched evidence for the current live model.

No retrospective result from this project can automatically authorize a live-model parameter change.
