# Live V3.11 crash-aware decision

## Decision

The project owner has explicitly asked that robustness improvements be reflected in the live model rather than remain visible only as research challengers.

V3.11 therefore promotes two **risk-control** changes while keeping the valuation core, fixed valuation references, curve slope and extreme threshold unchanged:

1. **Cheap-side overlay authority** — when the valuation z-score is below zero, the existing bounded earnings and macro overlays keep full ±6 percentage-point authority instead of being damped toward zero as valuation becomes extremely cheap. On the expensive side, the existing extreme-valuation damping is retained.
2. **Frozen SMA10 crash guard** — the pre-registered `trend-sma10-minus20-v1` rule becomes a one-way live risk brake: if the previous completed-month NIFTY 50 price close is strictly below the arithmetic mean of the latest 10 consecutive completed monthly closes, subtract 20 percentage points from the otherwise computed equity target, floored at 0. It never raises equity above the baseline target.

The final target remains clipped to 0–100% equity.

## Why this is a policy decision, not an alpha claim

The robust evaluation gate remains conservative. The historical valuation-core timing evidence did not pass the placebo, paired block-bootstrap or CSCV-PBO gates, and the frozen SMA10 challenger did not pass its pre-registered 5 percentage-point overall drawdown-improvement hurdle. Its reference test did improve maximum drawdown by about 1.37 percentage points overall and by about 4.67 percentage points in the COVID stress window, with about 0.46 percentage point lower CAGR.

Therefore this live change is **not** described as statistically proven market-timing skill or as an optimizer-selected winner. It is a transparent risk-budget choice: accept some possible return sacrifice in exchange for an explicit emergency brake while preserving the valuation-driven framework.

## Fail-closed data rule

The live allocation now also requires a fresh, internally consistent trend observation. If the previous completed-month close or its 10-month average cannot be verified, the final allocation is withheld rather than assuming risk-on.

## Governance retained

- No change to P/E, P/B/profitability, earnings-yield/G-sec or dividend-yield lens weights.
- No change to `k = 1.35` or `zc = 2.5`.
- No tuning of the 20 pp trend brake after seeing current market conditions; the value comes from the already frozen policy.
- Robust evaluation continues to report failures honestly.
- Future changes still require explicit review; a backtest cannot auto-promote itself.
