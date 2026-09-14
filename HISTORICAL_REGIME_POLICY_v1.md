# Historical Methodology Regime Policy v1

**Status:** subordinate to Institutional Validation Protocol v1; research only; zero live authority.

The project uses two different historical evidence tracks and must not mix their claims.

## Track A — current-definition reproduction

Purpose: determine whether the exact current NIFTY valuation definitions can be reproduced from point-in-time constituent evidence.

Rules:

- use only constituent/accounting information actually available by each signal date;
- preserve current methodology semantics exactly;
- do not bridge missing months with legacy published ratios, neutral fills or hindsight scaling;
- a pass strengthens data-lineage confidence only;
- it does not prove timing alpha or long-horizon efficacy.

The existing Sep-2023 to Aug-2026 blinded reconstruction pilot belongs to this track.

## Track B — long-horizon published-vintage timing evidence

Purpose: test whether a valuation-driven allocation hypothesis has timing value over a much longer certified point-in-time history.

A long sample may include official historical valuation series whose methodology changed over time. Those observations are admissible only when every month is tagged with the methodology regime actually in force and the first-available source is certified.

Rules:

1. **No hindsight rewriting.** A legacy published P/E/P/B/DY value is not converted into a later methodology merely to create a smoother history.
2. **Explicit regime boundaries.** Every known definition change is a structural break in the data model, not a cosmetic metadata field.
3. **No ex-post level stitching.** Do not multiply, shift or rescale an older regime to line up with a newer regime using overlap chosen after looking at strategy returns.
4. **Signal calibration is regime-aware.** Any standardisation across a break must use a rule frozen before outcome inspection. Acceptable designs include restarting expanding estimates within the new regime, using fixed ex-ante references justified independently of returns, or treating regime-normalised signals as separate blocks. The chosen design consumes a registered hypothesis if alternatives are compared on the same return matrix.
5. **Report regimes separately.** Publish efficacy by regime as well as any pooled result. A pooled result may not hide that all apparent edge came from one obsolete methodology era.
6. **Current-definition claim boundary.** A long historical timing pass does not establish that the current P/E/P/B definitions existed or were reproducible in earlier decades.
7. **Methodology uncertainty is adverse evidence.** If a break date, release rule or definition cannot be certified, the affected observations remain flagged/withheld; they are not silently assumed comparable.

## Claim hierarchy

- Track A can support: **current-definition reconstruction/data-lineage confidence**.
- Track B can support: **historical valuation-timing evidence under published-vintage regimes**.
- Neither track alone supports: **validated timing residual** or **institutionally validated allocation**. Those labels remain subject to the full institutional protocol, independent review and confirmation requirements.

## Why this separation exists

A 15-year or 20-year timing backtest is statistically more informative than a three-year current-definition sample, but it is economically misleading if it pretends historical valuation ratios were always defined exactly as they are today. Conversely, an exact recent current-definition reconstruction can be excellent data engineering while being far too short to establish investment efficacy.

The institutional process therefore keeps definition fidelity and long-horizon efficacy as separate scoreboards and only combines conclusions where the evidence genuinely overlaps.
