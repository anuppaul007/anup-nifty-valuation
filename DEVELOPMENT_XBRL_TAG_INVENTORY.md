# Development XBRL tag inventory

Status: **research only; zero live authority**.

This stage sits between the point-in-time filing-source map and numerical NIFTY reconstruction. Its purpose is to discover the exact accounting fact names that appear in the selected official NSE XBRL files before any accounting tag is authorized in code.

## Why this stage exists

Different filing templates, taxonomy revisions and company types can expose similar economics under different XBRL local names. A universal label guess would create a silent data-quality risk. Therefore this stage:

- reuses only the six visible development months;
- reuses the frozen Stage-B point-in-time filing selections;
- excludes company-months already marked as source gaps;
- downloads only official `nsearchives.nseindia.com` XML links selected by Stage B;
- stores a SHA-256 digest for every downloaded XBRL file;
- derives the template family from the official filename, including `BANKING_` separately from `INDAS_`;
- inventories context periods, fact local names and candidate facts related to profit, equity/net worth, bank capital/reserve structure, share capital, face value and EPS;
- does **not** authorize any candidate tag;
- does **not** calculate company earnings, market capitalisation, P/E, P/B, dividend yield or a NIFTY aggregate;
- does **not** fetch any holdout valuation target.

## First inventory findings

The first green inventory selected 270 unique structured XBRL files. **267/270** were still retrievable and parseable; the three unavailable historical XML links all belonged to INDUSINDBK (Dec-2022, Mar-2023 and Jun-2023 source periods) and returned 404. Those failures remain explicit archive defects rather than being silently substituted.

Across the retrievable structured universe:

- ordinary IndAS filings expose `ProfitOrLossAttributableToOwnersOfParent` as a strong consolidated-profit candidate, while `ProfitLossForPeriod` is more broadly present;
- banking templates use a distinct profit vocabulary including `ProfitLossForThePeriod` and require a separate mapping decision;
- `PaidUpValueOfEquityShareCapital` and `FaceValueOfEquityShareCapital` are broadly visible across both ordinary and banking templates and are useful candidates for reconstructing full-company shares outstanding;
- ordinary IndAS annual/equity contexts frequently expose `EquityAttributableToOwnersOfParent`;
- bank P/B must **not** inherit that ordinary-company equity mapping by assumption. The inventory now surfaces bank capital/reserve facts separately so an explicit bank net-worth rule can be reviewed before any numerical use.

These are discovery observations, not authorized accounting mappings.

## Evidence boundary

A green workflow proves that selected development XBRLs are retrievable and that their schemas can be inspected reproducibly. It does not prove that a candidate fact means the exact accounting concept required by Nifty Indices. That semantic mapping must be frozen separately and tested across template classes before numerical reconstruction.

The Stage-B residual source exceptions remain separate from this structured-XBRL inventory. Their absence does not permit renormalising the index or dropping them from a final reconstruction.

## Next gate

The next research version may create a template-specific mapping policy only after inspecting this inventory. It must define, at minimum:

1. exact profit concept used for each supported template;
2. quarterly versus year-to-date handling so TTM earnings are not double-counted;
3. consolidated versus standalone hierarchy;
4. annual net-worth/equity concept for ordinary companies;
5. a separately justified bank net-worth construction rather than borrowing an IndAS label;
6. paid-up share capital and face-value handling needed for full-company market capitalisation;
7. explicit treatment of NBFCs, insurers and non-XBRL first-party exception packets;
8. tests that reject ambiguous or multiple eligible facts rather than silently choosing one.

Any mapping change after the 30-month holdout is unsealed creates a new research version and cannot reuse that holdout as untouched validation.
