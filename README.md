# Anup Nifty Valuation — Web V3

Automated NIFTY 50 valuation and valuation-driven equity/debt allocation dashboard. A scheduled GitHub Action refreshes `data/latest.json` after the Indian market closes; the browser never needs API keys.

## Decision architecture

### 1. Fundamental valuation — the anchor

- NIFTY trailing P/E
- P/B adjusted partly for profitability/ROE
- earnings yield minus India 10-year G-sec
- dividend yield

Fundamental valuation determines the core equity allocation. The allocation curve may reach **100% equity at extreme undervaluation and 0% equity at extreme overvaluation**.

### 2. Earnings-cycle overlay

NIFTY EPS is derived as `index level / P/E`. The model tracks 12-month EPS growth and six-month growth acceleration.

### 3. Four-block macro overlay

Macro is intentionally split to reduce double-counting:

| Block | Weight | Inputs |
|---|---:|---|
| Global liquidity | 30% | US 10Y real yield, Fed assets, broad USD |
| India external / carry | 30% | Brent, India-US 10Y spread, India REER, USD/INR 1M forward premium |
| China industrial cycle | 20% | official NBS manufacturing PMI and new orders |
| Relative EM valuation | 20% | NIFTY valuation premium vs STOXX Emerging Markets ex-India |

Within each block, unavailable optional inputs are removed and the remaining weights are renormalized. Missing data are never silently treated as neutral.

**VIX is not directional.** It reduces deployment confidence/speed during stress, but a high VIX does not make cheap assets expensive.

The macro overlay is bounded to ±6 percentage points before damping. Earnings is also bounded to ±6 points. Both are multiplied by `1 - |fundamental valuation z| / extreme-z`, clipped to 0–1, so tactical overlays fade to zero at valuation extremes.

## Requested series and implementation choices

- **MSCI EM ex-India relative valuation:** the automated model uses the freely accessible STOXX Emerging Markets ex-India fundamentals as a licensing-friendly proxy. Historical archived factsheets are used to calibrate the normal India premium rather than assuming a fixed premium.
- **China Credit Impulse / Caixin PMI:** V3 uses official China NBS manufacturing PMI and new orders. It avoids proprietary Caixin/S&P data while preserving the industrial-cycle signal. A true PBOC credit-impulse module can be added later if a stable historical feed is established.
- **USD/INR forward premium:** best-effort CCIL 1-month implied differential. It is displayed immediately but excluded from the directional score until the dashboard has accumulated enough observations for its own calibration.
- **India REER:** BIS/FRED broad real effective exchange rate series.
- **US-India 10Y spread:** India 10Y less US 10Y, standardized against historical monthly spread data.

## Data sources

- NIFTY 50 level, P/E, P/B, dividend yield: Nifty Indices/NSE via `jugaad-data` helpers.
- India 10-year: FBIL daily par-yield table when available; FRED/OECD monthly series is a lagged fallback. Review/licence FBIL redistribution terms if the site becomes commercial.
- US real/nominal yields, broad USD, Brent, Fed assets and VIX: Federal Reserve/FRED.
- India REER: BIS series distributed through FRED.
- Emerging Markets ex-India fundamentals: STOXX.
- China manufacturing PMI/new orders: National Bureau of Statistics of China.
- USD/INR forward implied differential: CCIL public market table, best effort.

## Automation

`.github/workflows/refresh-data.yml` runs `scripts/update_data_v3.py` at **18:45 IST Monday–Friday**, and on model-code pushes. Data-only bot commits are ignored to prevent loops. Mandatory NIFTY inputs must validate before the last-known-good JSON is replaced.

## Next research milestone

Build a true walk-forward backtest with NIFTY 50 TRI and a debt TRI, recalculating every reference distribution using only information available at that historical date. Compare:

- 100% NIFTY TRI
- fixed 60/40
- fundamental-only Anup Valuation
- fundamental + earnings
- full V3 fundamental + earnings + macro

Evaluate CAGR, max drawdown, volatility, Sortino/Sharpe, rolling 1/3/5-year returns, turnover and realistic tax/friction assumptions. Use out-of-sample testing before changing model weights.
