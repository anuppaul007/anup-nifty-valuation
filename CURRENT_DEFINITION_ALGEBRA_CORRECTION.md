# Current-definition aggregation correction — signed denominators

Status: **research only**. No live V3.13 allocation, parameter, trend brake, earnings overlay, macro authority or prospective decision is changed by this correction.

## Why this correction exists

The first reconstruction helper represented index P/E and P/B as harmonic aggregates of constituent P/E/P/B values and required every constituent ratio to be positive. That is safe only for the special case in which every company has positive earnings and positive book value.

The current Nifty Indices P/E definition is broader: index earnings are the adjusted trailing-four-quarter earnings of all constituents **including profits and losses**. A loss-making constituent therefore remains part of the denominator. Only when the aggregate earnings of the index are negative does Nifty Indices stop computing/publishing index P/E until aggregate earnings become positive again.

Official definition:

- `https://www.niftyindices.com/resources/index-concepts/price-earnings-ratio`

The current P/B definition likewise starts from aggregate adjusted annual net worth/book value, not from a rule that every constituent must first have a positive P/B.

Official definition:

- `https://www.niftyindices.com/resources/index-concepts/price-to-book-value`

Dividend yield continues to use rolling-twelve-month equity dividends and the index market-capitalisation basis.

Official definition:

- `https://www.niftyindices.com/resources/index-concepts/dividend-yield`

## Controlling algebra for future reconstruction

For constituent `i`, let:

- `w_i` = the **actual published historical index weight** at the reconstruction date;
- `M_i` = company market capitalisation on a basis consistent with the financial numerator;
- `E_i` = point-in-time eligible TTM earnings, **signed**;
- `B_i` = point-in-time eligible annual net worth/book value, **signed if reported**;
- `D_i` = rolling-12-month eligible equity dividends by ex-date.

Then:

- `index earnings yield = Σ w_i × E_i / M_i`
- `index book yield = Σ w_i × B_i / M_i`
- `index dividend yield = Σ w_i × D_i / M_i`

and therefore:

- `PE_index = 1 / index earnings yield` only when aggregate earnings yield is positive;
- `PB_index = 1 / index book yield` when that denominator is non-zero;
- `DY_index = 100 × index dividend yield`.

This formulation is preferable to constituent P/E/P/B ratios because zero earnings can be represented exactly and negative earnings remain in the index denominator.

## Why the historical published weight is enough for aggregation

Suppose the index adjustment factor for a company is `f_i` (free-float/IWF/capping or the historical weighting treatment then in force). The published weight is proportional to `f_i × M_i`. Therefore:

`w_i × E_i/M_i` is proportional to `f_i × E_i`.

The same cancellation works for net worth and dividends. So when an exact historical index weight and a matching company market-cap basis are both known, the separate IWF need not be reconstructed merely to aggregate P/E, P/B and dividend yield. IWF history is still valuable as a cross-check of the weight construction and for any reconstruction period where exact published weights are missing.

## Strict gate

A future month can be called fully reconstructed only when all 50 constituent rows have:

- exact official membership and published historical index weight;
- consistent company market-cap basis;
- point-in-time eligible signed TTM earnings under the current consolidated/standalone fallback rule;
- point-in-time eligible annual net worth/book value under the current consolidated/standalone fallback rule;
- complete rolling-12-month dividends by ex-date;
- corporate-action continuity;
- no imputed company numerator.

A company is **not** rejected merely because earnings are zero/negative or net worth is negative. Missing evidence still fails closed.

## Repository implementation

`scripts/current_definition_aggregation.py` and `current_definition_aggregation_policy.json` are the controlling aggregation primitive/policy for future constituent reconstruction work. CI contains explicit loss-making, zero-earnings and negative-book-contribution tests.

The earlier positive-constituent-ratio helper in `scripts/current_definition_reconstruction.py` remains part of the historical Phase-1 feasibility code, but it is **superseded for future ratio reconstruction** and must not be used to certify a month. A later refactor may remove that legacy helper only after the source-probe code has been separated cleanly; this correction avoids silently rewriting historical research artifacts today.

## Evidence consequence

This correction does not create any new historical month, improve the timing t-statistic, change the current allocation or make the model more validated. It closes an algebraic source-fidelity defect before more historical data are assembled.
