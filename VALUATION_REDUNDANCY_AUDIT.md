# Valuation lens redundancy audit — V3.13

Status: **research only; no live allocation change.**

## Question

The live V3.13 valuation core combines four displayed lenses: P/E, log profitability-adjusted P/B, earnings yield minus the India government-bond yield, and dividend yield. They are useful economic views, but they are not four independent observations. This audit measures that dependence before any attempt to redesign weights.

The sample is restricted to the **36 fully current-definition monthly observations** from October 2023 through September 2026. It uses the exact V3.13 lens formulas and the frozen live weights. No return series is used to choose a parameter, and no weight is optimized.

## Result

| Diagnostic | Result |
| --- | ---: |
| P/E vs P/B-profitability correlation | **0.934** |
| P/B-profitability vs earnings-yield-gap correlation | **0.731** |
| P/E vs earnings-yield-gap correlation | **0.632** |
| Entropy effective rank of 4×4 correlation matrix | **2.21** |
| Participation-ratio effective rank | **1.72** |
| Correlation-matrix condition number | **57.2** |
| Effective lens count if live weights were uncorrelated | **3.57** |
| Correlation-adjusted effective lens count under live weights | **1.28** |
| Weighted signal-variance inflation vs uncorrelated lenses | **2.79×** |

The P/E and P/B-profitability variance-inflation factors are approximately **9.0** and **10.8**, respectively.

## Why this happens mechanically

P/E appears directly in three of the four formulas:

1. the P/E lens itself;
2. the P/B lens through index-implied profitability, `100 × P/B ÷ P/E`;
3. the earnings-yield spread through `100 ÷ P/E − government yield`.

For the log P/B lens, the numerator can be rearranged so its log sensitivities are **0.60 to log(P/E)** and **0.40 to log(P/B)** before normalization. The high observed correlation is therefore not surprising and should not be described as independent confirmation.

## Interpretation

This finding does **not** say valuation is useless, and it does not prove that any one lens should be removed. It says the current composite contains materially less independent information than a casual reading of “four valuation lenses” may imply.

The correct production interpretation is therefore:

> Four economic lenses are combined, but they are correlated views of a smaller number of underlying valuation dimensions. Agreement among them is not equivalent to four independent confirmations.

The 1.28 figure is a sample geometry diagnostic, not a confidence score, posterior probability, or stable population constant. The sample is only 36 months and the bond-yield history used in the monthly screen is not a certified release-vintage series.

## Governance decision

**No live weights are changed by this audit.** Reducing or reweighting lenses after seeing historical outcomes would create a new investment hypothesis and a new selection burden.

The next defensible step is to pre-register one covariance-aware or economically de-duplicated challenger **before** comparing investment outcomes. A candidate should use shrinkage/regularization because the current-definition sample is short and the raw correlation matrix is ill-conditioned. Any such challenger must enter the trial registry and pass the same exposure-matched, placebo, DSR/PBO, cost and prospective-evidence gates as other allocation hypotheses.

## Reproduce

```bash
python scripts/valuation_redundancy_audit.py
```

Machine-readable result: `data/valuation_redundancy_audit.json`.

The audit script fails if the V3.13 production constants change without an explicit corresponding update, so an old dependence result cannot silently be presented as applying to a new model.
