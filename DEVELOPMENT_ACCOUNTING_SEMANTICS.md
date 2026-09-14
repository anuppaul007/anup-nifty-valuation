# Development accounting semantics v1

Status: **research only; zero live authority; no index ratio computed**.

This stage freezes the accounting interpretation rules between point-in-time filing selection and numerical NIFTY reconstruction. Its purpose is to prevent target fitting: choosing an XBRL column, template family, profit concept, book-value construction or share-count rule after seeing which one best reproduces the six visible development valuation ratios.

## Current-period versus YTD is frozen first

Official NSE rendered result tables distinguish a current-period column labelled **“3 months/ 6 months ended”** from **“Year to date figures for current period ended”**. Historical Regulation-33 XBRL commonly represents these legacy columns as `OneD` and `FourD`.

Raw dates alone are unsafe because legacy contexts can share misleading start/end dates while carrying different reporting columns. V1 therefore freezes:

- `OneD` = current reporting period / quarter candidate;
- `FourD` = year-to-date current-period column;
- TTM earnings = exactly four consecutive signed `OneD` quarter facts;
- `FourD` values may not be summed into TTM;
- unknown or ambiguous contexts fail closed;
- a missing quarter may not be reconstructed from a later YTD value in this version.

## Profit candidates are template-specific and preregistered

**Ordinary IndAS**
1. `ProfitLossForPeriod` / `OneD`;
2. `ProfitOrLossAttributableToOwnersOfParent` / `OneD`.

**Banking**
1. `ProfitLossForThePeriod` / `OneD`;
2. `ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates` / `OneD`.

**NBFC_INDAS**
1. `ProfitLossForPeriod` / `OneD`;
2. `ProfitOrLossAttributableToOwnersOfParent` / `OneD`.

NBFC is deliberately separate from generic IndAS. The XBRL discovery stage found filenames such as `NBFC_INDAS_...`; matching the generic `INDAS_` token first would silently misclassify them. BAJAJFINSV is a concrete development example whose annual filing lacks the ordinary-company parent-equity fact.

Missing facts do not authorize an outcome-driven switch to another candidate. Development targets may compare only the frozen candidates. The 30-month holdout cannot choose among them.

## Annual book value / net worth remains unresolved where templates differ

Nifty Indices defines P/B using net worth from the annual financial report, preferring consolidated financials and using standalone only when consolidated is unavailable.

For ordinary IndAS, `EquityAttributableToOwnersOfParent` is preregistered as a candidate, not yet a universal authorization.

For the selected historical bank annual XBRLs, generic parent equity is absent while `ReserveExcludingRevaluationReserves` and paid-up capital are exposed. V1 therefore preregisters two separate bank candidates without promoting either:

- paid-up equity capital + `ReserveExcludingRevaluationReserves`;
- `Capital + ReservesAndSurplus` only where an annual balance-sheet filing explicitly exposes both total-company components.

NBFC annual book value is also separate. The BAJAJFINSV Mar-2023 filing exposes paid-up capital and `ReserveExcludingRevaluationReserves` but not `EquityAttributableToOwnersOfParent`, so V1 preregisters those as explicit competing NBFC constructions rather than borrowing the ordinary IndAS rule.

Insurance remains separate again. HDFCLIFE/SBILIFE must not be forced through IndAS, NBFC or banking mappings merely to increase coverage.

## Full-company market-cap basis has an independent sanity gate

Published index weights carry free-float/capping effects, but the signed-denominator algebra still requires a full-company market-cap basis consistent with each accounting numerator. V1 preregisters share-count candidates from paid-up equity capital and face value, but tag presence is **not** sufficient.

Every inferred share count must be reconciled against point-in-time official corporate actions and adjacent filings. Legitimate jumps from mergers, bonuses, splits or other capital actions remain eligible only after reconciliation. Orders-of-magnitude jumps without an official capital action fail closed. The observed ICICIBANK Mar/Jun-2023 paid-up-capital anomaly is explicitly a development defect to resolve before numerical reconstruction.

## Development qualification hurdle was not invented after seeing results

The semantic policy reuses the already-preregistered reconstruction limits:

- every one of the six development months must be complete with no imputation;
- P/E and P/B relative error must be ≤2% each month and median ≤1%;
- dividend-yield absolute error must be ≤0.05 percentage point each month and median ≤0.025 point.

If several complete candidate families pass, they remain explicit alternatives until a source-semantic reason resolves them. The numerically closest development fit is not automatically chosen. Failure keeps the mapping unresolved; it does not permit easier thresholds or holdout inspection.

## Fail-closed numerical handling

- losses and negative values are preserved;
- XBRL `scale` is applied exactly once;
- `decimals` is precision metadata, not another multiplier;
- segment/dimensional facts are ineligible for total-company earnings/net worth;
- unequal duplicate facts for the same exact concept/context are rejected;
- four TTM quarter ends must be distinct and consecutive;
- every source must already satisfy its point-in-time dissemination cutoff.

## Gate before numerical reconstruction

The XBRL inventory must first pass its own retrieval/taxonomy gate. Then every concept, context, unit, sign, scale, duplicate rule, consolidated/standalone hierarchy, bank/NBFC/insurance treatment and share-count continuity rule must be deterministic. Only then may the six visible development targets be used. The holdout remains sealed throughout.

Primary methodology references:

- Nifty Indices — Price/Earnings Ratio: `https://www.niftyindices.com/resources/index-concepts/price-earnings-ratio`
- Nifty Indices — Price to Book Value: `https://www.niftyindices.com/resources/index-concepts/price-to-book-value`

This stage has no authority over V3.13, the live equity/debt allocation, trend brake, macro authority or evidence-promotion rules.
