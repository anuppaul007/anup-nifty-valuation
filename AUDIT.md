# V3.4 model and data audit — 11 September 2026

This review distinguishes reproducible arithmetic, data defects, and unvalidated investment assumptions. V3.4 repairs the identified defects. It does not establish that this strategy maximizes returns.

## What the quoted V3.3 snapshot proves

The quoted calculation is reproducible from the saved 10 September NIFTY snapshot at repository commit `84ec34d83c5b6518c3c1d60b8db46cbf00e08b05`:

| Component | Reproduced result |
| --- | ---: |
| Effective macro coverage | 53.0% |
| Available-factor macro score | -0.306191 |
| Fundamental equity allocation | 83.0795% |
| Earnings adjustment | -1.0998 percentage points |
| Original macro adjustment | -1.0517 percentage points |
| Original final equity target | 80.9280% |

The weighting arithmetic was correct for those supplied scores. That does not validate the source data or the investment model.

## Findings and corrections

| Finding | Consequence | V3.4 correction |
| --- | --- | --- |
| STOXX parser selected the risk table. The supposed P/E of 23.9 was annualized volatility; the supposed P/B of 0.8 and dividend yield of 0.3 were Sharpe ratios. | Incorrect relative valuation inputs and contaminated calibration history. This block was not yet scored, so these wrong inputs did not directly change the quoted 80.9% allocation. | Bind to named trailing-fundamentals headers and the exact index row. The inspected 31 July 2026 factsheet instead reports P/E including losses 17.2, P/B 2.1, dividend yield 3.1%. Reject legacy calibration entries. |
| Repeated current quotes could be stored under refresh months, pairing old EM data with current NIFTY ratios. | Artificial history and mismatched comparison dates. | Pair NIFTY with the actual EM observation month, deduplicate that month, and require 12 distinct earlier valid observations. No archive download or historical backfill is claimed. |
| Insufficient or constant macro history returned zero in some paths. | Missing calibration could appear neutral and receive full coverage. | Return an absent score; only finite, calibrated scores contribute weight. |
| Missing China new orders could contribute a zero while coverage stayed complete. | Overstated China coverage. | Keep the available PMI contribution and lower internal coverage to 70% if new orders are absent. |
| Effective block weights were renormalized, but the total macro budget was not reduced for missing overall coverage. | An incomplete macro set could still use the entire 6-point budget. | Retain the renormalized score and multiply the final macro budget by effective coverage as an explicit robustness policy. |
| Cached values had few observation dates; an overall refresh timestamp could make old inputs look current. India 6.88% was undated. | Stale values could affect present recommendations. | Record source observation dates and eligibility separately. Use a dated RBI near-10-year government bond, dated FBIL par yield, or explicitly lagged monthly fallback. Undated or stale yields cannot establish an allocation target. |
| Broad fallback could preserve prior active macro scores. | Outages might still show an active recommendation based on old macro data. | Isolate source fetches and scoring failures. Whole-block failure invalidates scores and coverage rather than promoting a cached payload to live status. |
| Treasury calibration used only the current year's data. Fed DownloadTable could return CSV to an HTML parser. | Calibration reset in January; Fed assets could remain unavailable. | Fetch current and three earlier Treasury calendar years. Support CSV and HTML Fed responses with separate FRED alternatives. |
| Daily dollar data and earnings comparisons could use a partial current month against completed historical months. | Inconsistent cycle comparisons. | Use completed months; preserve missing calendar months. Standardization references exclude the observation being scored. |
| Fundamental weights labelled as percentages summed to 95. A normal CDF of the composite was labelled a percentile. | Misleading presentation of weights and statistical meaning. | Display normalized weights summing to 100%; label the composite a fixed-reference z-score, not an empirical percentile. |
| Expected premium used fixed growth, terminal valuation and debt-return assumptions. Deployment confidence was a heuristic without deployment-speed implementation. | Apparent forecasts and confidence beyond what was implemented. | Remove the return-premium forecast. Describe the retained data/stress indicator accurately; it does not execute or schedule trades. |
| Failed browser reload could leave an earlier allocation visible. Scheduled bot commits do not trigger a branch-based Pages rebuild. | Old numbers could persist after an error or after a successful data refresh. | Clear allocation on failed reads; load the public main-branch JSON directly with cache bypass. Opening/reloading the page reads published data; it does not run the providers. |

Primary checks: [STOXX factsheet](https://stoxx.com/index/swexiagv/?factsheet=true), [RBI current rates and dated government securities](https://www.rbi.org.in/), [GitHub Pages publishing-source documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site). These are changing sources; the dates above identify the inspected observations.

## Coverage policy: the numerical effect

For each block, effective weight = strategic weight × eligible internal weight. The macro score is the weighted mean over available blocks. The final macro adjustment is:

`macro score × 6 percentage points × effective coverage × valuation damping`

Holding every old score and fundamental input constant, the coverage-budget change alone reduces the old macro adjustment from -1.0517 to -0.5574 percentage points. That mechanical comparison gives 81.4223% equity instead of 80.9280%. It is **not a refreshed recommendation**: corrected source dates, the bond yield, completed-month earnings and macro histories must also be refreshed.

## Investment-model limits that remain

- Fundamental reference levels/scales, the profitability adjustment, logistic slope, extreme thresholds and overlay weights are retained assumptions. They are exposed on the dashboard; the repo has no verified point-in-time estimation procedure for them.
- P/E, P/B and earnings yield share inputs. Their weighted combination is not independent evidence, a measured probability, or proof of intrinsic fair value. P/B divided by P/E is an implied profitability proxy; index-methodology and aggregation differences can matter.
- STOXX EM ex-India Universal All Cap and NIFTY 50 differ in size, sector and country composition and valuation conventions. Even a correct relative premium is not automatically mispricing. This block stays inactive until its calibration requirement is met.
- Macro directions are economic hypotheses, not estimated causal effects. Brent futures include contract-roll effects. RBI's near-10-year bond is a traded-bond proxy, not the exact FBIL constant-maturity par series; the selected instrument and source are displayed. Monthly yield fallbacks can lag market conditions.
- The 0–100% curve is preserved. Extreme valuations do not identify a market bottom or top, and an allocation target is not an instruction to trade the whole portfolio immediately. Near-term spending and emergency reserves sit outside this allocation sleeve.
- No walk-forward comparison against NIFTY total returns and investable debt total returns, taxes, costs, turnover, drawdown or alternative portfolios exists yet. Neither maximum return nor suitability for a particular person's liabilities is established. A debt allocation is an asset-class target, not an assumption that all debt instruments are risk-free.
- Automatic daily refresh does not guarantee every provider updates daily. The dashboard distinguishes the file refresh date, individual observation dates, missing factors and calibration eligibility.

## Verification

The review adds 12 Python tests and 7 JavaScript tests covering adversarial source tables, quoted multi-series CSV selection, source-date binding, missing calibration, partial coverage, independent source failure, completed months, unchanged snapshot arithmetic, coverage attenuation, attainable 0/100 endpoints, stale inputs, and failed-reload clearing. The tests run before the scheduled data refresh. The native GitHub refresh is the integration check for NSE and live external providers; its result is available in the repository's Actions history.

The first integration run also identified the Fed's short `DownloadTable.aspx` preview, which does not supply the requested calibration history. The fallback now requests `Output.aspx`, parses quoted CSV correctly and selects the named series. Browser data reads prefer the public repository API, with a raw-file fallback, to reduce branch-CDN propagation delays. The Fed has announced DDP changes for November 2026; future endpoint retirement must remain a visible source failure, not an invented neutral score.
