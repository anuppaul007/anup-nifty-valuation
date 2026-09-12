# Anup Multi-Asset Research Layer

This layer is deliberately separate from the existing NIFTY V3.6 model. It does not change the NIFTY valuation engine or its equity/debt research signal.

## Portfolio structure

The **retirement core** always sums to 100% across four sleeves:

- NIFTY 50 equity
- Debt
- Gold
- Silver

The starting equity/debt ratio is the existing V3.6 research signal. Gold and Silver are then carved proportionally from Equity and Debt. This preserves the relative stance of the NIFTY model while adding diversifiers.

**Bitcoin is not included in that 100%.** It is shown only as a separate tactical signal, consistent with treating crypto outside the retirement core.

## Gold score

Gold score =

- 35% US 10Y real-yield regime — lower real yields are supportive
- 25% broad-USD 3-month momentum — a weaker dollar is supportive
- 25% Gold 12-month momentum
- 15% VIX stress — higher stress is modestly supportive

Gold target = `13% + 5% × Gold score`, clipped to **8–18%**.

## Silver score

Silver score =

- 45% Gold/Silver ratio relative value — an unusually high ratio is supportive for Silver
- 30% China/global industrial-cycle score
- 25% Silver 12-month momentum

Silver target = `3.5% + 3.5% × Silver score`, clipped to **0–7%**.

Gold + Silver are capped at 25% of the retirement core.

## Bitcoin tactical signal

BTC score =

- 30% price versus 200-day average
- 20% 12-month momentum
- 25% existing global-liquidity block
- 25% drawdown/value signal versus the recent 3-year high

The tactical signal is discretised to **0%, 2.5%, 5%, 7.5% or 10%**. This is **not** deducted from the retirement-core 100% allocation and should not be interpreted as a validated retirement allocation.

## Data policy

Gold, Silver and BTC price histories are fetched from Yahoo Finance (`GC=F`, `SI=F`, `BTC-USD`). The layer reuses the already-verified V3.6 US real-yield, broad-dollar, VIX, global-liquidity and China-industrial inputs. Missing or stale required data withhold the affected research allocation; missing values are never filled with a neutral score.

## Validation status

This is **research-v1**. The weights, target ranges and score mappings are transparent assumptions and are **not backtest-optimized**. The next required step is a dedicated historical multi-asset backtest with Gold and Silver over the longest reliable common history and BTC only from the point where reliable BTC history exists. Before BTC exists, its weight must be zero rather than backfilled or invented.
