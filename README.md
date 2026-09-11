# Anup Nifty Valuation — Web V3.4

Automatic NIFTY valuation research dashboard with a valuation-driven equity/debt target. Opening the website loads the latest published data. No daily data entry or browser API key is needed.

[Open dashboard](https://anuppaul007.github.io/anup-nifty-valuation/) · [Detailed audit](AUDIT.md)

## Allocation model

Fundamental valuation remains the anchor. P/E, profitability-adjusted P/B, earnings yield minus India ~10-year government yield, and dividend yield receive normalized weights of 31.58%, 26.32%, 31.58%, and 10.53%. P/B divided by P/E is an implied profitability proxy, not independently measured ROE.

Fixed reference levels and scales are in `model.js` and visible on the dashboard. They are retained assumptions, not automatically estimated fair values or optimized portfolio parameters. The allocation curve reaches 100% equity at composite z <= -2.5 and 0% at z >= +2.5. Separately required spending and emergency reserves remain outside this allocation sleeve.

Earnings is an index-implied EPS cycle overlay using completed-month 12-month growth and six-month growth acceleration. It is bounded to 6 percentage points before coverage and valuation damping.

| Macro block | Strategic weight | Internal weights |
| --- | ---: | --- |
| Global liquidity | 30% | US real yield 50%; Fed assets 25%; broad dollar 25% |
| India external / carry | 30% | Brent 35%; India-US spread 30%; India REER 20%; forward premium 15% |
| China industrial cycle | 20% | Official NBS manufacturing PMI 70%; new orders 30% |
| EM ex-India relative valuation | 20% | Dated same-month NIFTY/STOXX P/E and P/B premium, subject to calibration |

Missing, stale and uncalibrated factors receive no score. Within each block, available scores are renormalized. Effective block weight is strategic weight times available internal weight. Macro score is the average using these effective weights.

`macro adjustment = score × 6 pp × effective coverage × damping`

`damping = max(0, 1 - abs(fundamental z) / 2.5)`

Both overlays vanish at valuation extremes. The data/stress indicator uses VIX and coverage as a heuristic; it is not statistical confidence, a probability of profit, or implemented deployment-speed control. There is no automated trading.

## Sources and dates

- NIFTY: NSE/Nifty Indices through `jugaad-data`; price and ratio histories are aligned by date. History begins in May 2021. Earnings and dollar momentum use completed months.
- India yield: the RBI government-securities section supplies a dated bond near 10-year maturity, with instrument identity shown. Dated FBIL par yield is an alternative; FRED/OECD monthly India 10-year is an explicitly lagged fallback. A traded benchmark bond and a constant-maturity par yield are related proxies, not identical series.
- US yields: U.S. Treasury daily files for this and the three preceding calendar years. Fed assets and broad USD use FRED/Federal Reserve independently. VIX uses CBOE. Brent uses Yahoo Finance futures history, approximately 63 trading observations for three-month momentum.
- India REER: BIS/FRED. India-US spread needs a dated current yield and sufficient overlapping monthly calibration. USD/INR forwards remain excluded pending a dependable dated adapter and history.
- China: official NBS manufacturing PMI and new orders; this is not Caixin PMI or a credit-impulse series.
- EM: STOXX Emerging Markets ex India Universal All Cap, using named trailing fundamentals including negative earnings. The actual source month is matched to NIFTY. Twelve earlier distinct valid months are required before scoring. The system accumulates valid observations; it does not claim an archived-factsheet backfill. Incorrect legacy calibration is rejected.

Eligibility limits are explicit policy choices: NIFTY, daily yields, Brent and VIX 7 calendar days; Fed assets 15; monthly dollar 75; China and earnings 70; REER and EM 100. The monthly India yield fallback uses a 100-day limit and is marked lagged. The website excludes overlays if the published packet is over 3 days old or has an unsupported schema. Cached data retain their source dates. If mandatory NIFTY data are invalid, the updater preserves the saved file; if a valid dated bond yield is missing, the website withholds the allocation while showing the remaining diagnostics.

## Automatic refresh and hosting

GitHub Pages continues to host the website. `.github/workflows/refresh-data.yml` runs `scripts/update_data_v3.py` at **18:45 IST on weekdays**, on code pushes, or through workflow dispatch. GitHub schedules can be delayed, and provider data may lag. Tests run first. NIFTY validation and atomic file replacement prevent partial JSON publication.

The browser reads the public repository's latest `data/latest.json` through the GitHub API with cache bypass and a raw-file fallback. This avoids depending on a Pages rebuild or raw-CDN propagation for every update. Data commits made using `GITHUB_TOKEN` do not trigger a branch-based Pages rebuild. **Reload published data** reads that file; it does not trigger provider downloads. Weekends and holidays show the last available observation and its date.

## Validation and research still required

Run `python -m unittest discover -s tests -p 'test_*.py' -v` and `node --test tests/model.test.cjs`. The GitHub workflow also checks the complete live-provider pipeline.

Before treating these targets as an investment strategy, a point-in-time walk-forward backtest must compare NIFTY total returns, investable debt total returns, fixed 60/40, valuation-only, earnings-overlay and full-model variants. It must include taxes, transaction costs, turnover, drawdowns and out-of-sample tests. Current weights and outputs are research rules; maximum return has not been demonstrated.
