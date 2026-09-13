# Development accounting source map — current-definition reconstruction

Status: **research only; zero live authority**.

This stage does not calculate a reconstructed NIFTY valuation ratio. It freezes the point-in-time source-selection mechanics for the six development months before numerical XBRL field mappings are added.

## Scope

- Development only: Sep-2023 through Feb-2024.
- The 30 holdout official P/E/P/B/dividend-yield targets remain sealed.
- Official NIFTY constituent symbols, closes and weights come from the monthly NSE Indices weight PDFs already covered by the Stage-A completeness gate.

## Public-information cutoff

For each official month-end constituent snapshot, a company filing is eligible only if its exchange dissemination timestamp is no later than **15:30 on that snapshot date**. If the exchange dissemination timestamp is absent, broadcast timestamp and then filing date are used as explicit fallbacks.

This conservative cutoff prevents a result disclosed after the market close from being pulled backward into that day's reconstruction. If development-month comparison later shows that NSE Indices operationally incorporated a different same-day cutoff, that discrepancy must be documented before any holdout unsealing.

## P/E source chain

For each constituent and signal date, the mapper requires four distinct eligible reporting period ends and prefers consolidated financial results at every period. Standalone is used only when an eligible consolidated filing for that period is unavailable, and every fallback period is recorded.

This source rule follows the current NSE Indices P/E definition: trailing-four-quarter constituent profits and losses are cumulated, consolidated financials are preferred, and standalone is a fallback where consolidated financials are unavailable.

## P/B source

The mapper separately selects the latest eligible annual filing, again preferring consolidated. Numerical parsing later must extract annual net worth/book value rather than substituting quarterly book values.

## Why this stage exists before numerical parsing

NSE filings use multiple templates, including IndAS, banking and insurance-specific formats. Some valid historical or special-template issuers can return HTTP 200 with zero rows from a generic symbol-filtered endpoint. The mapper therefore records both a default symbol request and an explicit historical date-window request. Zero rows remain a source-routing gap; they are not filled from secondary finance sites.

## Market-capitalisation discipline

The official constituent PDF's `Index Mcap` is the free-float/capping-adjusted contribution used by the index. It is **not** directly paired with unadjusted company earnings or annual net worth. The later numerical stage must establish a consistent full-company market-cap/shares basis or an independently reproduced adjustment factor.

## Next gate

Only after this source map identifies a complete, reviewable filing chain for each development constituent-month will template-specific numerical parsers be frozen. The numerical development reconstruction must then reproduce the six visible official development targets before the 30-month holdout can be unsealed.

Passing any of these stages strengthens data-lineage confidence only. It does not establish allocation alpha or authorize any V3.13 parameter change.
