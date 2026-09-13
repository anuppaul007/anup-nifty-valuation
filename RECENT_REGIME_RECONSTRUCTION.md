# Recent-regime current-definition reconstruction — blinded pilot

Status: **research only; zero live authority**.

This project addresses the largest remaining data-lineage gap in the NIFTY valuation model: can we independently reconstruct the official NIFTY 50 P/E, P/B and dividend yield from constituent-level information that was actually public at each month-end?

## Why this is separate from performance backtesting

A successful reconstruction would show that the valuation inputs can be reproduced from company evidence under the current accounting definitions. It would **not** show that the allocator beats a static portfolio, that the 66.7% point target is optimal, or that the SMA10 policy adds alpha.

## Frozen sample before holdout inspection

The sample is fixed at 36 completed months from **Sep-2023 through Aug-2026**.

- Development: **Sep-2023 through Feb-2024** (6 months).
- Holdout: **Mar-2024 through Aug-2026** (30 months).

The six development targets may be inspected while accounting mappings and parsers are built. The 30 holdout official P/E/P/B/dividend-yield targets must not be fetched or stored by the source-harvest code until the reconstruction implementation and mappings are frozen.

The exact tolerances are preregistered in `recent_reconstruction_policy_v1.json`. Passing them strengthens **data integrity only**. It does not authorize a model promotion.

## Stage A — source harvest

`scripts/recent_regime_reconstruction_pilot.py`:

1. downloads the official NSE Indices monthly market-capitalisation/weightage archive for every month in the frozen sample;
2. isolates the NIFTY 50 constituent PDF and requires exactly 50 security rows with a near-100% displayed weight sum;
3. parses the **official historical symbol, close price, Index Mcap and weight** directly from that PDF, including wrapped security-name rows;
4. exposes official dashboard valuation targets for the six development months only;
5. deliberately does not request holdout dashboard targets;
6. cross-checks historical symbols against the current NSE equity security master without using that master to invent historical membership;
7. probes NSE financial-results and corporate-action APIs for every unique historical symbol in the 36-month sample and records coverage rather than silently substituting another source;
8. writes an artifact containing source hashes and coverage gaps rather than inventing missing data.

### Important market-cap distinction

The PDF's `Index Mcap` is the constituent's **index-adjusted market-cap contribution**. It is extremely useful for verifying weights and historical membership, but it is not automatically interchangeable with the full-company market-capitalisation denominator needed to combine unadjusted company earnings, book value and dividends.

The accounting reconstruction must either recover a consistent full-company market-cap basis (for example from price × point-in-time shares outstanding) and let the historical index weight absorb the IWF/capping factor, or independently reconstruct the corresponding adjustment factor. `Index Mcap` must not be substituted into the signed-denominator formula while using unadjusted company fundamentals.

## Stage B — constituent accounting engine

After Stage A source coverage is verified, the next implementation must assemble, for every constituent and month:

- actual historical index weight;
- matching full-company market-capitalisation basis;
- signed TTM consolidated earnings known by the signal date, with standalone fallback only where consolidated data were unavailable;
- signed latest eligible annual net worth/book value;
- rolling-12-month cash dividends by ex-date;
- corporate-action continuity and share-capital consistency.

The signed-denominator algebra in `scripts/current_definition_aggregation.py` is mandatory. Loss-making constituents cannot be removed or neutral-filled.

## Stage C — freeze, then unseal

Only after the symbol set, accounting tags, share-capital rules and reconstruction code are frozen in a reviewable commit may the 30 holdout official target values be fetched. Any post-unseal mapping/rule change creates a new research version; the old holdout cannot be reused as untouched confirmation evidence.

## Failure is informative

A missing source, parser failure, unavailable filing, unresolved corporate action or tolerance miss is recorded as a defect/gap. It is not repaired with interpolation, cross-sectional imputation or a methodology scaling factor.
