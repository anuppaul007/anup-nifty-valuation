# Development residual source resolution

Status: **research only; zero live authority**.

The generic NSE financial-results route produced a clean baseline source map for **270 of 300** development company-months. The remaining 30 gaps are concentrated in only five symbols: HDFCLIFE, SBILIFE, LTIM, TATAMOTORS and NESTLEIND.

This stage resolves those gaps without changing the reconstruction targets or looking at the 30-month holdout.

## Frozen residual rules

- **LTIM → LTM**: query the current security identity in addition to the historical symbol because NSE changed the symbol to LTM in April 2026.
- **TATAMOTORS → TMPV**: query the continuing listed security identity in addition to the historical symbol because NSE changed the symbol to TMPV in October 2025 after the demerger/name-change mechanics.
- **HDFCLIFE / SBILIFE**: the generic financial-results endpoint can return zero records even though official life-insurance filings exist. Use official NSE corporate-announcement attachments as a fallback and extract the current reporting quarter from the official PDF.
- **NESTLEIND**: for the development period, allow an audited consolidated 31-Dec result as the latest annual book source when the generic Annual endpoint omits the historical calendar-year filing.

All fallbacks remain official NSE/NSE-archive evidence. Secondary finance websites are prohibited.

## What this stage does not do

It does not parse profit, net worth, paid-up share capital, face value or dividends. It therefore cannot yet claim that P/E, P/B or dividend yield has been independently reconstructed. It only resolves the point-in-time source chain needed for the later accounting parser.

A failed residual remains a published gap. It is not neutral-filled or imputed. The official holdout valuation targets remain sealed.
