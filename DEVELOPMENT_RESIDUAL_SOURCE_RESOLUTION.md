# Development residual source resolution

Status: **research only; zero live authority**.

The generic NSE financial-results route produced a clean baseline source map for **270 of 300** development company-months. The remaining 30 gaps are concentrated in only five symbols: HDFCLIFE, SBILIFE, LTIM, TATAMOTORS and NESTLEIND.

This stage resolves those gaps without changing the reconstruction targets or looking at the 30-month holdout.

## Frozen residual rules

- **LTIM → LTM**: source-routing may query the current symbol only for the same continuing listed security, frozen by ISIN `INE214T01019` and official NSE symbol-change evidence. The LTIM→LTM symbol change was effective 27-Feb-2026; the later company-name change to LTM Limited was effective 17-Apr-2026.
- **TATAMOTORS → TMPV**: source-routing may query the current symbol only for the continuing listed security with ISIN `INE155A01022`, supported by the frozen NSE demerger/name/symbol reference. It is not permission to substitute a different demerged entity.
- **HDFCLIFE / SBILIFE**: the generic financial-results endpoint can return zero records even though official life-insurance filings exist. Use official NSE corporate-announcement attachments as a fallback and identify the reporting quarter from narrow official metadata/PDF rules.
- **NESTLEIND**: only this residual symbol may use the explicitly frozen first-party Nestlé India investor-result packets hosted on `www.nestle.in`. The frozen development source sequence covers 30-Sep-2022, 31-Dec-2022, 31-Mar-2023, 30-Jun-2023, 30-Sep-2023 and 31-Dec-2023. Source publication date must be strictly before the monthly signal date.

## Nestlé transition-year guardrail

Nestlé India changed from a January–December financial year to April–March through a **15-month transition year ending 31-Mar-2024**. Therefore:

- the 31-Dec-2022 packet remains the latest frozen **audited annual** book source for every development signal from Sep-2023 through Feb-2024;
- the 31-Dec-2023 packet may enter the TTM quarter chain after its 7-Feb-2024 publication;
- the 31-Dec-2023 twelve-month result is explicitly **unaudited** and may not replace the audited 2022 annual book source.

This issuer fallback was frozen before any numerical accounting extraction and before any holdout valuation target was opened. It is narrowly scoped to a documented NSE-history gap for NESTLEIND and does not silently generalize to other constituents.

## Evidence hierarchy

The default hierarchy remains official NSE structured results → official NSE/NSE-archive filing evidence. A narrowly preregistered first-party issuer packet may be used only where the policy explicitly names the issuer, periods, publication dates and URLs. Secondary finance websites, interpolation, neutral filling and index renormalisation are prohibited.

The CI gate requires all **30/30 residual company-months** to have a complete TTM and annual source chain, which lifts the six-month development source map to **300/300 company-months**. Any unavailable or semantically inconsistent frozen packet causes the gate to fail rather than silently dropping the constituent.

## What this stage does not do

It does not parse profit, net worth, paid-up share capital, face value or dividends. It therefore cannot yet claim that P/E, P/B or dividend yield has been independently reconstructed. It only resolves the point-in-time source chain needed for the later accounting parser.

The official 30-month holdout valuation targets remain sealed, and this stage has no authority over V3.13.
