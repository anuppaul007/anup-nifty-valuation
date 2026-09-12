# Protocol-style long-history backtest

Status: **exploratory research only**. This work does not change the live V3.6
allocator or any prospective archived decision.

## Why this exists

The older Jan-2000 study used one pre-Apr-2006 debt-return proxy. That cache is
a genuine OECD/FRED India short-term interest-rate series, but it is not the RBI
policy repo series and it is not an investable debt total-return index. The
purpose of this study is to make that assumption explicit and test whether the
headline conclusion survives reasonable alternatives.

## Debt proxy audit

Three full-history debt variants are reported before the ICICI Prudential Short
Term Fund NAV becomes available in Apr-2006:

1. `oecd_short_rate`: prior-month cached OECD/FRED India short-term rate,
   accrued monthly.
2. `rbi_policy_rate`: prior-month RBI repo/policy/LAF rate from the historical
   screen, accrued monthly. This is a sensitivity proxy, not an investable
   return series.
3. `conservative_cash`: the lower of those two rates minus 1 percentage point,
   floored at zero, accrued monthly.

From Apr-2006 onward all three variants use the same observed short-term debt
fund NAV return.

RBI annual reports independently verify that 91-day Treasury-bill yields are a
more natural government short-rate benchmark. Verified annual weighted-average
91-day cut-off yields include 6.88% (2001-02), 5.73% (2002-03), and 4.63%
(2003-04). A complete month-by-month 2000-06 auction-derived total-return
series has **not** yet been reconstructed, so partial observations are not
silently filled or promoted to the full-period backtest.

## Portfolio mechanics

The equity sleeve uses NIFTY 50 TRI. At the start of each month the current
portfolio weight is the weight that drifted after the prior month's equity and
debt returns. Rebalancing occurs only when the target gap reaches the selected
band: 0, 5, or 10 percentage points. Costs are charged on one-way capital
turnover at 0, 10, or 25 bps. Initial deployment is not charged as rebalancing
turnover.

The report also includes NIFTY 50 TRI buy-and-hold and 60/40 annual-rebalance
benchmarks.

## Limits

This is not the full prospective validation protocol. The historical allocation
screen is the common-factor valuation reconstruction; pre-2021 NIFTY valuation
methodology is not directly comparable with the current consolidated regime;
historical release vintages are not fully verified; and the report uses monthly
rather than daily drawdown. It is therefore labelled **exploratory, unverified
vintages** and cannot by itself authorize a live-model change.
