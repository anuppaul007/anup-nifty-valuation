# Development accounting semantics v1

Status: **research only; zero live authority; no index ratio computed**.

This stage freezes the accounting interpretation rules that sit between point-in-time filing selection and numerical NIFTY reconstruction. The purpose is to prevent a subtle form of target fitting: choosing an XBRL column or accounting concept after seeing which one reproduces the six visible development valuation ratios best.

## Why the column rule must be frozen first

Official NSE rendered financial-result tables distinguish a current-period column labelled **“3 months/ 6 months ended”** from a separate **“Year to date figures for current period ended”** column. Historical Regulation-33 XBRL commonly represents those legacy columns with context IDs `OneD` and `FourD`, respectively.

The historical development inventory also shows why dates alone are unsafe: some legacy files attach the same or misleading start/end dates to `OneD` and `FourD` even though their values clearly represent different reporting columns. Therefore v1 treats the column/context identity as authoritative only when the expected legacy structure is present. Unknown or ambiguous contexts fail closed.

Frozen rule:

- `OneD` = current reporting period / quarter candidate;
- `FourD` = year-to-date current-period column;
- TTM earnings may sum **exactly four consecutive signed `OneD` quarter facts**;
- `FourD` values may not be summed into TTM;
- missing current-quarter facts may not be reverse-engineered from later YTD figures in this version.

## Competing profit concepts are preregistered, not chosen yet

For ordinary IndAS files, v1 preregisters two candidates:

1. `ProfitLossForPeriod` / `OneD`;
2. `ProfitOrLossAttributableToOwnersOfParent` / `OneD`.

The first has much broader coverage in the retrieved development XBRLs. The second is economically closer to parent-equity-holder profit but is absent in a meaningful subset of files. Its absence is not permission to switch concepts opportunistically within the same candidate.

For banking files, v1 preregisters:

1. `ProfitLossForThePeriod` / `OneD`;
2. `ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates` / `OneD`.

Those two values differ in many bank filings. Neither is promoted in this stage.

The six development months may later compare the frozen candidates under a preregistered reproduction tolerance. The 30-month holdout may not be used to choose between them.

## Annual book value / net worth remains template-specific

Nifty Indices defines P/B using net worth from the annual financial report, preferring consolidated financials and using standalone only when consolidated financials are unavailable.

For ordinary IndAS files, `EquityAttributableToOwnersOfParent` is preregistered as the current net-worth candidate.

Banking filings expose a different balance-sheet structure. NSE rendered banking statements explicitly show **Capital** and **Reserves and surplus**, so v1 preregisters `Capital + ReservesAndSurplus` as a bank net-worth candidate but does **not** authorize it yet. Minority-interest/other-equity treatment must be fixed before any development P/B comparison.

Insurance templates remain separate. HDFCLIFE/SBILIFE must not be forced through an IndAS or banking mapping merely to increase coverage.

## Full-company market-cap basis

The signed-denominator reconstruction uses published index weights to carry free-float/capping effects. It still requires a full-company market-cap basis consistent with the accounting numerator. V1 therefore preregisters share-count candidates from paid-up equity capital and face value, with corporate-action continuity as a mandatory gate. No automatic fallback is allowed merely because one share-capital tag is missing.

## Fail-closed numerical handling

- losses and negative values are preserved;
- an XBRL `scale` attribute, when present, is applied as `value × 10^scale`;
- `decimals` is precision metadata, not an additional scale multiplier;
- segment/dimensional facts are ineligible for total-company earnings/net worth;
- unequal duplicate facts for the same exact concept/context are rejected;
- four TTM quarter ends must be distinct and consecutive;
- every filing must already have passed the point-in-time dissemination cutoff.

## What must happen before any development ratio is reconstructed

The XBRL inventory/retrieval stage must pass its own evidence gate (or be replaced by an explicitly versioned frozen-manifest design independent of valuation outcomes). Numerical concept, context, unit, sign, scale, duplicate handling and consolidated/standalone hierarchy must be deterministic. Banks, insurers and ordinary companies remain separate where their reporting templates differ.

Only after those conditions are frozen may the six visible development targets be used to evaluate the preregistered accounting candidates. If none meets the preregistered reproduction hurdle, the mapping stays unresolved. The holdout remains sealed.

Primary methodology references:

- Nifty Indices — Price/Earnings Ratio: `https://www.niftyindices.com/resources/index-concepts/price-earnings-ratio`
- Nifty Indices — Price to Book Value: `https://www.niftyindices.com/resources/index-concepts/price-to-book-value`

This research stage has no authority over V3.13, the live equity/debt allocation, the trend brake, macro authority or evidence-promotion rules.
