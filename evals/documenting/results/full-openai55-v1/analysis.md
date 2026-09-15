# Frozen full-suite analysis

Recommendation: **retain_B**

Manifest: `b23dcb8a583f222bd98f20c97574c2ca47c0a955e8897d7a3d7d92fccd341cba`

## Primary judgments (swaps excluded)

Positive scores favor B for AB and C for BC. Missing jobs are excluded from valid-repetition means and counted separately.

| Split | Pair | Valid/planned jobs | Scored/planned cases | + wins | − wins | Ties | Uncertain | Missing | Equal-case effect | 95% interval |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| development | AB | 36/36 | 12/12 | 1 | 2 | 33 | 0 | 0 | -0.0278 | [-0.0833, 0.0278] |
| development | BC | 36/36 | 12/12 | 1 | 3 | 32 | 0 | 0 | -0.0556 | [-0.1389, 0.0278] |
| holdout | AB | 72/72 | 24/24 | 0 | 9 | 63 | 0 | 0 | -0.1250 | [-0.2083, -0.0556] |
| holdout | BC | 71/72 | 24/24 | 4 | 1 | 66 | 0 | 1 | 0.0417 | [0.0000, 0.0972] |

## Decision gates

- **positive_primary_interval**: fail. `{   "passed": false,   "interval": [     0.0,     0.09722222222222221   ] }`
- **paired_requirement_nonincrease**: pass. `{   "passed": true,   "B": 0.0,   "C": 0.0,   "C_minus_B": 0.0,   "contributing_cases": 24,   "absolute_roundoff_tolerance": 1e-12,   "relative_roundoff_tolerance": 0.0,   "tolerance_note": "Numerical roundoff only; not a material noninferiority margin." }`
- **coverage**: pass. `{   "passed": true,   "scope": "held-out primary BC judgments",   "valid_jobs": {     "numerator": 71,     "denominator": 72,     "rate": 0.9861111111111112   },   "minimum_valid_fraction": 0.9,   "minimum_valid_repetitions_per_case": 2,   "insufficient_cases": [],   "cases_meeting_minimum": {     "numerator": 24,     "denominator": 24,     "rate": 1.0   } }`
- **critical_review**: pass. `{   "passed": true,   "status": "not_adjudicated",   "all_critical_flag_occurrences": 0,   "C_critical_flag_occurrences": 0,   "C_flagged_writer_ids": [],   "confirmed_new_critical_regressions": null,   "secondary_adjudication_required": false }`

Eligibility is conditional evidence under the frozen plan, not proof. Critical flags and substantive disputes require source-grounded secondary adjudication; this program does not confirm or dismiss them.

## Paired secondary measures

Fractions are averaged within repetition/document, then equally across contributing documents. B is kept separate in AB and BC.

| Split | Pair | Measure | Negative arm | Positive arm | Difference | Contributing cases | Contributing jobs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| development | AB | requirement_failure_fraction | 0.0000 | 0.0000 | 0.0000 | 12 | 36 |
| development | AB | requirement_uncertainty_fraction | 0.0000 | 0.0000 | 0.0000 | 12 | 36 |
| development | AB | known_issue_resolution | 1.0000 | 1.0000 | 0.0000 | 9 | 27 |
| development | AB | organization | 5.0000 | 5.0000 | 0.0000 | 12 | 36 |
| development | AB | unnecessary_change | 0.6111 | 0.6389 | 0.0278 | 12 | 36 |
| development | BC | requirement_failure_fraction | 0.0000 | 0.0000 | 0.0000 | 12 | 36 |
| development | BC | requirement_uncertainty_fraction | 0.0000 | 0.0000 | 0.0000 | 12 | 36 |
| development | BC | known_issue_resolution | 1.0000 | 0.9815 | -0.0185 | 9 | 27 |
| development | BC | organization | 5.0000 | 5.0000 | 0.0000 | 12 | 36 |
| development | BC | unnecessary_change | 0.7222 | 0.5556 | -0.1667 | 12 | 36 |
| holdout | AB | requirement_failure_fraction | 0.0000 | 0.0000 | 0.0000 | 24 | 72 |
| holdout | AB | requirement_uncertainty_fraction | 0.0000 | 0.0000 | 0.0000 | 24 | 72 |
| holdout | AB | known_issue_resolution | 1.0000 | 1.0000 | 0.0000 | 18 | 54 |
| holdout | AB | organization | 5.0000 | 5.0000 | 0.0000 | 24 | 72 |
| holdout | AB | unnecessary_change | 0.6667 | 0.7361 | 0.0694 | 24 | 72 |
| holdout | BC | requirement_failure_fraction | 0.0000 | 0.0000 | 0.0000 | 24 | 71 |
| holdout | BC | requirement_uncertainty_fraction | 0.0000 | 0.0000 | 0.0000 | 24 | 71 |
| holdout | BC | known_issue_resolution | 1.0000 | 1.0000 | 0.0000 | 18 | 53 |
| holdout | BC | organization | 5.0000 | 5.0000 | 0.0000 | 24 | 71 |
| holdout | BC | unnecessary_change | 0.6667 | 0.5833 | -0.0833 | 24 | 71 |

## Order consistency

planned: 54, eligible: 54, incomplete: 0, agreements: 49, disagreements: 5, decisive_reversals: 0.
Incomplete pairs have null agreement, not disagreement.

## Regression flags

Unique primary-assessed writer IDs per severity; repeated AB/BC assessments do not multiply writer counts.

| Split | Arm | Severity | Flagged/assessed writers | Flag occurrences |
| --- | --- | --- | --- | --- |
| development | A | critical | 0/36 | 0 |
| development | A | major | 0/36 | 0 |
| development | A | minor | 0/36 | 0 |
| development | B | critical | 0/36 | 0 |
| development | B | major | 0/36 | 0 |
| development | B | minor | 0/36 | 0 |
| development | C | critical | 0/36 | 0 |
| development | C | major | 0/36 | 0 |
| development | C | minor | 0/36 | 0 |
| holdout | A | critical | 0/72 | 0 |
| holdout | A | major | 0/72 | 0 |
| holdout | A | minor | 0/72 | 0 |
| holdout | B | critical | 0/72 | 0 |
| holdout | B | major | 0/72 | 0 |
| holdout | B | minor | 2/72 | 2 |
| holdout | C | critical | 0/71 | 0 |
| holdout | C | major | 0/71 | 0 |
| holdout | C | minor | 0/71 | 0 |

All original flags (including swaps), quotations, explanations, and selected judgments are preserved in `analysis.json` for secondary review.

## Word counts and clean controls

| Split | Arm | Group | Selected/planned writers | Equal-case words | Word ratio | Literal unchanged | Ignoring one final LF | LF-only change |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| development | A | all | 36/36 | 502.3889 | 0.9613 | 0/36 | 0/36 | 0/36 |
| development | A | clean-controls | 6/6 | 583.0000 | 0.9852 | 0/6 | 0/6 | 0/6 |
| development | B | all | 36/36 | 468.1667 | 0.8957 | 0/36 | 0/36 | 0/36 |
| development | B | clean-controls | 6/6 | 536.0000 | 0.9068 | 0/6 | 0/6 | 0/6 |
| development | C | all | 36/36 | 472.4444 | 0.9045 | 0/36 | 3/36 | 3/36 |
| development | C | clean-controls | 6/6 | 567.3333 | 0.9598 | 0/6 | 3/6 | 3/6 |
| holdout | A | all | 72/72 | 629.4861 | 0.9727 | 0/72 | 0/72 | 0/72 |
| holdout | A | clean-controls | 12/12 | 688.0000 | 1.0096 | 0/12 | 0/12 | 0/12 |
| holdout | B | all | 72/72 | 572.2917 | 0.8804 | 0/72 | 0/72 | 0/72 |
| holdout | B | clean-controls | 12/12 | 602.0833 | 0.8779 | 0/12 | 0/12 | 0/12 |
| holdout | C | all | 72/72 | 577.0278 | 0.8925 | 0/72 | 0/72 | 0/72 |
| holdout | C | clean-controls | 12/12 | 615.3333 | 0.9064 | 0/12 | 0/12 | 0/12 |

Whitespace-delimited words; ratios are descriptive, not quality scores. Frozen draft comparison ignores at most one terminal LF only where labeled.

## Operational reliability and all-attempt usage

### development / writers

```json
{
  "planned": 108,
  "attempted": 108,
  "attempts": 108,
  "statuses": {
    "valid": 108
  },
  "valid_coverage": {
    "numerator": 108,
    "denominator": 108,
    "rate": 1.0
  },
  "first_attempt_validity": {
    "numerator": 108,
    "denominator": 108,
    "rate": 1.0
  },
  "retry_recovery": {
    "numerator": 0,
    "denominator": 0,
    "rate": null
  },
  "terminal": 108
}
```

| Token bucket | Sum | Known attempts | Unknown attempts |
| --- | --- | --- | --- |
| input | 168941 | 108 | 0 |
| output | 71015 | 108 | 0 |
| reasoning | 3343 | 108 | 0 |
| cache_read | 0 | 108 | 0 |
| cache_write | 0 | 108 | 0 |
- seconds: 2668.0988378730003; known attempts 108, unknown 0.
- reported_cost: 0.0; known attempts 108, unknown 0.

### development / judges

```json
{
  "planned": 90,
  "attempted": 90,
  "attempts": 90,
  "statuses": {
    "valid": 90
  },
  "valid_coverage": {
    "numerator": 90,
    "denominator": 90,
    "rate": 1.0
  },
  "first_attempt_validity": {
    "numerator": 90,
    "denominator": 90,
    "rate": 1.0
  },
  "retry_recovery": {
    "numerator": 0,
    "denominator": 0,
    "rate": null
  },
  "terminal": 90
}
```

| Token bucket | Sum | Known attempts | Unknown attempts |
| --- | --- | --- | --- |
| input | 417187 | 90 | 0 |
| output | 171377 | 90 | 0 |
| reasoning | 107255 | 90 | 0 |
| cache_read | 118272 | 90 | 0 |
| cache_write | 0 | 90 | 0 |
- seconds: 5340.099779752997; known attempts 90, unknown 0.
- reported_cost: 0.0; known attempts 90, unknown 0.

### holdout / writers

```json
{
  "planned": 216,
  "attempted": 216,
  "attempts": 217,
  "statuses": {
    "valid": 216
  },
  "valid_coverage": {
    "numerator": 216,
    "denominator": 216,
    "rate": 1.0
  },
  "first_attempt_validity": {
    "numerator": 215,
    "denominator": 216,
    "rate": 0.9953703703703703
  },
  "retry_recovery": {
    "numerator": 1,
    "denominator": 1,
    "rate": 1.0
  },
  "terminal": 216
}
```

| Token bucket | Sum | Known attempts | Unknown attempts |
| --- | --- | --- | --- |
| input | 397892 | 216 | 1 |
| output | 178200 | 216 | 1 |
| reasoning | 9719 | 216 | 1 |
| cache_read | 2432 | 216 | 1 |
| cache_write | 0 | 216 | 1 |
- seconds: 6377.526508009001; known attempts 217, unknown 0.
- reported_cost: 0.0; known attempts 216, unknown 1.

### holdout / judges

```json
{
  "planned": 180,
  "attempted": 180,
  "attempts": 190,
  "statuses": {
    "failed": 1,
    "valid": 179
  },
  "valid_coverage": {
    "numerator": 179,
    "denominator": 180,
    "rate": 0.9944444444444445
  },
  "first_attempt_validity": {
    "numerator": 170,
    "denominator": 180,
    "rate": 0.9444444444444444
  },
  "retry_recovery": {
    "numerator": 9,
    "denominator": 10,
    "rate": 0.9
  },
  "terminal": 180
}
```

| Token bucket | Sum | Known attempts | Unknown attempts |
| --- | --- | --- | --- |
| input | 991380 | 184 | 6 |
| output | 394445 | 184 | 6 |
| reasoning | 254197 | 184 | 6 |
| cache_read | 243584 | 184 | 6 |
| cache_write | 0 | 184 | 6 |
- seconds: 12340.821392419995; known attempts 184, unknown 6.
- reported_cost: 0.0; known attempts 184, unknown 6.

## Jobs without a selected valid result

| Role | Job | Split | Status | Terminal |
| --- | --- | --- | --- | --- |
| judges | blind-dup-seatforge-hold-decision-r1-BC-primary | holdout | failed | True |

## Validator/transport failures

| Role | Job | Attempt | Classification |
| --- | --- | --- | --- |
| writers | blind-tech-cobaltkey-cutover-advisory-rb26-r2-B | 1 | transport |
| judges | blind-cons-contour-routing-decision-r2-AB-primary | 1 | interrupted |
| judges | blind-dup-badgewake-receipt-incident-r2-BC-swap | 1 | interrupted |
| judges | blind-dup-seatforge-hold-decision-r1-BC-primary | 1 | schema_or_evidence |
| judges | blind-dup-seatforge-hold-decision-r1-BC-primary | 2 | schema_or_evidence |
| judges | blind-org-brindle-job-endpoints-r2-AB-primary | 1 | interrupted |
| judges | blind-org-velora-replica-recovery-r1-AB-primary | 1 | interrupted |
| judges | blind-rep-pulsebox-platform-tabs-r1-BC-swap | 1 | schema_or_evidence |
| judges | blind-rep-pulsebox-platform-tabs-r2-AB-primary | 1 | schema_or_evidence |
| judges | blind-rep-pulsebox-platform-tabs-r3-AB-primary | 1 | schema_or_evidence |
| judges | blind-tech-anchorvault-restore-faq-rb26-r1-BC-primary | 1 | interrupted |
| judges | blind-tech-cobaltkey-cutover-advisory-rb26-r2-BC-primary | 1 | interrupted |

Full metadata, failure messages, first-attempt/retry usage, per-document denominators, and incomplete order-pair details are in `analysis.json`.

## Interpretation and limitations

- Held-out BC is the sole confirmatory confidence family. AB and development intervals are secondary/descriptive; no multiplicity-adjusted claims are made.
- Only valid primary repetitions are averaged within each document, followed by equal document weighting. Missing jobs are not uncertain outcomes or zero scores.
- Intervals condition on observed documents within planned categories; wholly missing categories give no interval. Coverage gates remain mandatory.
- Bootstrap units are documents within category, never repetitions or swaps. Scheduling/statistical seeds do not establish independence of model randomness.
- Requirement uncertainty is reported separately from failure. Clean documents with no known issues contribute null resolution, not zero.
- The manifest's own hash and selected native artifact hashes are checked; equality with live sources is intentionally not required.
- Analysis reads a metadata snapshot and does not lock ongoing execution. In-progress, blocked, failed, and pending jobs remain visible; regenerate after completion.
- Only the full judge contract's recognized fields are scored. Original selected findings are retained without programmatic adjudication.
- Synthetic fixed-draft finalization with frozen prompts; not initial drafting, normal agent tools, automatic skill loading, or evidence of universal model behavior
- Review critical flags and substantive disputed findings against sources; retain original assessments and label secondary AI-assisted review
- All retained attempts contribute usage, including failed attempts. Five token buckets are kept separate.
- Missing usage is unknown; adapter zero placeholders without observed steps are not observed zero usage.
- Retry recovery denominator is attempted jobs without a valid first attempt, including unfinished jobs.
- Semantic requirement failures, regression flags, and uncertainty on valid judgments are outcomes, not validator failures.
- Recorded failure_kind takes precedence over error wording; only schema_or_evidence outcomes are refined into schema or evidence failures.
- Generic schema-or-evidence failures cannot be separated retrospectively from their metadata.
- Reported cost is not subscription billing; provider retries are unavailable. Summed adapter seconds are not batch wall time.
