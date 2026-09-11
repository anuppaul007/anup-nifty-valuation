# Anup Nifty Valuation — Web V2

This is a deployable upgrade of the supplied single-file dashboard. The page remains static and fast; a scheduled Python job refreshes `data/latest.json` after the Indian market closes.

## Model architecture

1. **Fundamental valuation anchor** — trailing P/E, profitability-adjusted P/B, earnings-yield minus India 10-year G-sec, dividend yield, and the existing low-weight trend check.
2. **Earnings-cycle overlay** — derived NIFTY EPS (`index level / P/E`), 12-month EPS growth and its 6-month acceleration.
3. **Global macro/liquidity overlay** — US 10-year real yield, broad USD, Brent and Federal Reserve assets. VIX is displayed as a confidence/stress variable, not a directional valuation factor.
4. **Portfolio controller** — existing debt floor, hard bounds, deadband, rate limit and review cadence.

The tactical overlay is deliberately bounded (default ±6 percentage points from macro and ±6 from earnings) and is multiplied by a damping factor `1 - |valuation z| / extreme-z`. It therefore fades to zero at valuation extremes: the model can still reach **100% equity when extremely cheap and 0% when extremely dear**.

## Why this is safer than browser-side scraping

The browser reads only a local JSON file. Data-site failures, CORS and keys never reach the user. The updater validates mandatory fields before replacing the last good file. The UI flags a feed older than three days as stale.

## Free hosting: recommended setup

### Cloudflare Pages + GitHub Actions

1. Create a GitHub repository and put this folder at its root.
2. Push to `main`.
3. In Cloudflare: **Workers & Pages → Create → Pages → Connect to Git** and choose the repository.
4. No framework/build command is required; set the output directory to `.` (repository root).
5. GitHub Actions runs at 18:45 IST on weekdays and commits a refreshed `data/latest.json`. Each commit automatically triggers a Cloudflare Pages deployment.
6. Use the generated `*.pages.dev` URL, or add your own domain later.

At this traffic/data volume the stack is designed to fit free tiers.

## Data sources

- NIFTY 50 level, P/E, P/B, dividend yield: Nifty Indices/NSE historical reports, retrieved by the current `jugaad-data` index helper.
- India 10-year: FBIL daily par-yield table when it can be read; FRED/OECD monthly series is a lagged fallback. **If the site becomes commercial or public at scale, review/licence the FBIL redistribution terms or replace this feed with a licensed source.**
- Global macro: FRED CSV series `DFII10`, `DTWEXBGS`, `DCOILBRENTEU`, `WALCL`, `VIXCLS`.

## Important next improvement: a real walk-forward backtest

The legacy chart is intentionally left labelled as a behaviour check. A production V3 should use monthly NIFTY 50 TRI and a debt TRI, calculate calibration only from information available at each historical date, and compare the core and core+macro systems against 100% NIFTY and fixed 60/40. Measure CAGR, volatility, max drawdown, Sortino, rolling 1/3/5-year returns, turnover and realistic tax/friction assumptions.

## Local test

Do not double-click `index.html` if you want automatic JSON loading. Run:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000/`.

`data/latest.json` in this package is a seed/fallback. The first successful scheduled/manual GitHub Action replaces it.
