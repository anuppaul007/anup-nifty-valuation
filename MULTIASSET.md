# Anup Multi-Asset Research Layer

This layer is deliberately separate from the existing NIFTY V3.6 model. It does not change the NIFTY valuation engine or its equity/debt research signal.

## Portfolio structure

The **retirement core** always sums to 100% across four sleeves:

- NIFTY 50 equity
- Debt
- Gold
- Silver

The starting equity/debt ratio is the existing V3.6 research signal. Research-v1 then carves Gold and Silver proportionally from Equity and Debt. That preserves the original Equity/Debt ratio, but the funding rule is now explicitly tested against equity-first and debt-first alternatives in the robustness audit rather than assumed to be optimal.

**Bitcoin is not included in that 100%.** It is shown only as a separate tactical signal, consistent with treating crypto outside the retirement core.

## Gold score

Gold score =

- 35% US 10Y real-yield regime — lower real yields are supportive
- 25% broad-USD 3-month momentum — a weaker dollar is supportive
- 25% Gold 12-month momentum
- 15% VIX stress — higher stress is modestly supportive

Gold target = `13% + 5% × Gold score`, with a defensive allocation band of **8–18%**. The band is a safety constraint; it is not treated as evidence that the live formula frequently reaches both endpoints.

## Silver score

Silver score =

- 45% Gold/Silver ratio relative value — an unusually high ratio is supportive for Silver
- 30% China/global industrial-cycle score
- 25% Silver 12-month momentum

Silver target = `3.5% + 3.5% × Silver score`, with a defensive allocation band of **0–7%**.

Gold + Silver are capped at 25% of the retirement core.

## Bitcoin tactical signal

BTC score =

- 30% price versus 200-day average
- 20% 12-month momentum
- 25% existing global-liquidity block
- 25% drawdown/value signal versus the recent 3-year high

The tactical signal is discretised to **0%, 2.5%, 5%, 7.5% or 10%**. This is **not** deducted from the live retirement-core 100% allocation and should not be interpreted as a validated retirement allocation.

Momentum and drawdown/value are intentionally different lenses and can disagree near turning points. The V2 audit therefore reports how often they oppose each other and evaluates BTC only over the BTC-available era so a pre-BTC crisis cannot dominate the reported BTC drawdown.

## Data policy

Gold, Silver and BTC price histories are fetched from Yahoo Finance (`GC=F`, `SI=F`, `BTC-USD`). The layer reuses the verified macro sources used by the project for US real yield, broad USD, VIX, global liquidity and the China industrial cycle. Missing or stale required live data withhold the affected research allocation; missing values are never filled with a neutral score.

Historical Gold/Silver/BTC returns in the research backtest are continuous USD market-price series converted to synthetic INR with BIS USD/INR. They are useful research proxies, but they are not Indian ETF total-return series and therefore remain an implementation limitation rather than a claim of exact investable returns.

## Historical validation

The project now runs a long-history multi-asset backtest from January 2000 onward. Gold/Silver are activated only when their required historical signals are genuinely available, and BTC is zero before reliable BTC history exists.

The backtest is deliberately labelled research rather than proof because:

- the base NIFTY history is the project's common-history valuation reconstruction rather than a release-vintage reconstruction of the complete modern V3.6 stack;
- historical macro series are latest-revised rather than vintage releases;
- synthetic INR market-price returns omit ETF expense ratios, tracking error, taxes and exit loads;
- published factor weights were not selected by an optimizer.

## Robustness audit V2

`scripts/multiasset_robustness.py` produces `data/multiasset_robustness.json` and tests the questions that matter before changing real capital allocation:

1. **Dynamic versus static metals** — research-v1 is compared with simple static Gold/Silver allocations on the same eligible history. If dynamic timing cannot beat a simple static diversifier on risk-adjusted evidence, complexity is not justified.
2. **Funding rule** — proportional carve is compared with equity-first and debt-first funding.
3. **Gold/Silver ratio horizon** — 3-year, 5-year, 7-year, 10-year and expanding windows are compared, including a median/MAD robust variant.
4. **Factor ablation** — every Gold and Silver factor is removed one at a time and the remaining weights are renormalised. A factor that does not improve robustness becomes a candidate for deletion.
5. **Parameter perturbation** — 500 deterministic variants perturb factor weights and score-to-allocation mappings around the published assumptions. This is a stability test, not an optimizer; the best historical parameter set is never promoted automatically.
6. **BTC-era isolation** — funded-BTC research is evaluated only from the period in which BTC signals and returns exist, with signal-bucket performance and momentum-versus-value disagreement reported separately.

All comparison metrics include a **10 bps one-way turnover sensitivity** and report CAGR, maximum drawdown, annualised volatility, Calmar and Sortino where defined.

## Governance

The robustness audit is intentionally unable to change the live model. `live_model_change_authorized` remains false in the audit output. Any future change to funding rules, factor weights, lookbacks or target mappings requires explicit review of the evidence and remains subordinate to the project's prospective walk-forward governance.
