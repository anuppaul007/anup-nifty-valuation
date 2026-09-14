# Point-in-Time Panel Specification v1

**Status:** research/data-governance contract; zero live allocation authority.

This specification turns “point-in-time data” into an auditable storage contract. A historical value is not considered certified merely because it has an old date. The project must be able to show **what the value represented, when it became public, what raw source supplied it, which methodology regime was in force, and why that exact observation was eligible at the decision timestamp**.

## 1. Three physically/logically separate layers

### A. Source-observation panel

One row per raw or reconstructed economic observation. It retains all known vintages/revisions rather than overwriting history.

Required information includes:

- stable observation ID;
- entity/security/index identity and symbol as reported at the time;
- field ID and raw value;
- normalized numeric value and unit;
- economic period start/end and observation date;
- raw publication/dissemination timestamp;
- availability timestamp actually used by the model;
- availability-rule ID;
- retrieval timestamp;
- source URI and SHA-256 of raw bytes;
- filing/release ID;
- methodology regime;
- accounting scope/template family;
- consolidated/standalone and audited/unaudited status where relevant;
- revision sequence;
- eligibility/ambiguity status and notes.

### B. Decision panel

One row for each field used at each monthly decision timestamp. It points to the exact source-observation row selected and records:

- decision timestamp in IST;
- selected observation ID;
- value/unit used;
- age of the observation;
- methodology regime;
- transformation version;
- selection reason;
- eligibility status.

A decision row may not silently disappear because data are inconvenient. Missing, ambiguous, stale, after-cutoff or unsupported observations must appear as explicit statuses.

### C. Outcome panel

Equity/debt total returns, instrument implementation data and their source hashes are stored separately from signal construction.

The signal and outcome panels may be joined for strategy evaluation only after the following are frozen:

1. panel version and manifest;
2. exact trial family;
3. cost and tax profile;
4. evaluator commit and statistical gates.

This separation does not magically make historical research untouched, but it creates a strong anti-leakage audit trail and prevents return outcomes from becoming an undocumented data-cleaning input.

## 2. Availability is not the same as period end

For exchange filings, use the strongest available dissemination evidence in this order unless a source-specific policy is stricter:

1. exchange dissemination timestamp;
2. broadcast timestamp;
3. filing timestamp;
4. conservative date-only rule.

If only a publication date is known, treat it conservatively as end-of-day (or use the stricter preregistered source rule). A source published on the decision date cannot be used for that decision unless its dissemination time proves it was public before the cutoff.

Later revisions may be stored, but they may not be backfilled into earlier decisions.

## 3. Raw evidence is immutable

Every selected source must have a URI, retrieval timestamp and SHA-256 raw-byte hash. All known revisions are retained. A newer revision creates another observation/vintage; it does not overwrite the earlier value that was actually available.

Secondary finance sites may be used as diagnostics or to find a primary source, but they may not fill a missing certified primary observation.

## 4. Fail-closed statuses

At minimum the panel distinguishes:

- eligible and selected;
- eligible but superseded by a later eligible revision available before cutoff;
- after cutoff;
- missing;
- source route unavailable;
- archive not found;
- ambiguous;
- unsupported template;
- stale;
- methodology incompatible;
- withheld by policy.

Only explicitly eligible rows may feed a decision. A “neutral” value is not a missing-data policy.

## 5. Accounting and transformation integrity

Where NIFTY methodology prefers consolidated financials, consolidated is preferred and standalone fallback is recorded explicitly. Losses/negative values are retained. Units and XBRL scale/sign handling must be auditable.

Every transformed field references an exact transformation version. Raw values remain stored separately so an outside reviewer can reconstruct the transformation independently.

## 6. Methodology-regime integrity

Every row carries a methodology-regime ID. Current-definition reconstruction and long published-vintage history remain separate evidence tracks under `HISTORICAL_REGIME_POLICY_v1.md`.

No earlier P/E/P/B/DY series may be silently rewritten to a later definition. Any long-history pooled timing analysis must use a preregistered regime-handling rule and publish regime-specific outcomes.

## 7. Outcome series integrity

The outcome panel stores, at minimum:

- decision ID;
- return start/end timestamps;
- equity total return;
- debt total return;
- source IDs and source hashes for both sleeves;
- implementation regime ID.

The primary debt sleeve is chosen for low-duration defensive/dry-powder characteristics before strategy-return inspection, not because one debt series maximizes the backtest.

## 8. Manifest and certification report

Every built panel version publishes a manifest containing:

- panel version;
- builder commit SHA;
- row count and date range;
- field coverage;
- methodology-regime counts;
- missing/status counts;
- source-hash manifest;
- final output-file SHA-256.

A panel is not “certified” merely because the build script completed. Certification fails if any selected row:

- lacks a source hash;
- became public after the decision cutoff;
- is ambiguous;
- lacks a methodology regime;
- lacks a transformation version;
- was silently dropped from a required decision field.

## 9. Relation to the current reconstruction pilot

The existing six-month development / 30-month blinded holdout pilot remains a **current-definition reconstruction track**. Its filing-source map, accounting semantics, symbol continuity rules, archive defects and source hashes should feed this schema rather than be replaced by a different ad hoc format.

The long-history panel is a later expansion of the same provenance discipline. It may use certified historical published vintages under explicit methodology regimes; it may not pretend that later current definitions existed unchanged in earlier years.

## 10. Evidence boundary

Passing this panel contract demonstrates better historical data integrity. It does **not** demonstrate that the allocation rule has alpha, improves retirement outcomes, or should replace the current live model.

Timing efficacy remains governed by `INSTITUTIONAL_VALIDATION_PROTOCOL_v1.md`.
