# Frozen full-suite analysis

Recommendation: **retain_B**

Manifest: `04e80bcebfe83733aeac0127506711de385aed077411b4dda09980c2376e0a0b`

## Primary judgments (swaps excluded)

Positive scores favor B for AB and C for BC. Missing jobs are excluded from valid-repetition means and counted separately.

| Split | Pair | Valid/planned jobs | Scored/planned cases | + wins | − wins | Ties | Uncertain | Missing | Equal-case effect | 95% interval |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| development | AB | 35/36 | 12/12 | 7 | 8 | 20 | 0 | 1 | 0.0000 | [-0.1667, 0.1667] |
| development | BC | 35/36 | 12/12 | 6 | 6 | 23 | 0 | 1 | -0.0139 | [-0.1528, 0.1250] |
| holdout | AB | 31/72 | 17/24 | 7 | 4 | 20 | 0 | 41 | 0.1176 | [-0.0686, 0.3039] |
| holdout | BC | 34/72 | 20/24 | 5 | 5 | 24 | 0 | 38 | -0.0417 | [-0.1083, 0.0250] |

## Decision gates

- **positive_primary_interval**: fail. `{   "passed": false,   "interval": [     -0.10833333333333332,     0.025   ] }`
- **paired_requirement_nonincrease**: pass. `{   "passed": true,   "B": 0.0,   "C": 0.0,   "C_minus_B": 0.0,   "contributing_cases": 20,   "absolute_roundoff_tolerance": 1e-12,   "relative_roundoff_tolerance": 0.0,   "tolerance_note": "Numerical roundoff only; not a material noninferiority margin." }`
- **coverage**: fail. `{   "passed": false,   "scope": "held-out primary BC judgments",   "valid_jobs": {     "numerator": 34,     "denominator": 72,     "rate": 0.4722222222222222   },   "minimum_valid_fraction": 0.9,   "minimum_valid_repetitions_per_case": 2,   "insufficient_cases": [     {       "case": "blind-clean-indexer-release-8f3c",       "valid_repetitions": 1     },     {       "case": "blind-clean-recovery-window-note-a9e5",       "valid_repetitions": 0     },     {       "case": "blind-cons-northstar-cutover-bulletin",       "valid_repetitions": 1     },     {       "case": "blind-cons-solstice-field-dictionary",       "valid_repetitions": 1     },     {       "case": "blind-dup-badgewake-receipt-incident",       "valid_repetitions": 1     },     {       "case": "blind-org-brindle-job-endpoints",       "valid_repetitions": 1     },     {       "case": "blind-org-peregrine-render-options",       "valid_repetitions": 1     },     {       "case": "blind-org-velora-replica-recovery",       "valid_repetitions": 1     },     {       "case": "blind-rep-bellweather-loan-procedures",       "valid_repetitions": 0     },     {       "case": "blind-tech-anchorvault-restore-faq-rb26",       "valid_repetitions": 1     },     {       "case": "blind-tech-petalgrid-ingest-contract-rb26",       "valid_repetitions": 0     },     {       "case": "blind-tech-prismtrace-window-reference-rb26",       "valid_repetitions": 0     }   ],   "cases_meeting_minimum": {     "numerator": 12,     "denominator": 24,     "rate": 0.5   } }`
- **critical_review**: pass. `{   "passed": true,   "status": "not_adjudicated",   "all_critical_flag_occurrences": 0,   "C_critical_flag_occurrences": 0,   "C_flagged_writer_ids": [],   "confirmed_new_critical_regressions": null,   "secondary_adjudication_required": false }`

Eligibility is conditional evidence under the frozen plan, not proof. Critical flags and substantive disputes require source-grounded secondary adjudication; this program does not confirm or dismiss them.

## Paired secondary measures

Fractions are averaged within repetition/document, then equally across contributing documents. B is kept separate in AB and BC.

| Split | Pair | Measure | Negative arm | Positive arm | Difference | Contributing cases | Contributing jobs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| development | AB | requirement_failure_fraction | 0.0000 | 0.0000 | 0.0000 | 12 | 35 |
| development | AB | requirement_uncertainty_fraction | 0.0000 | 0.0000 | 0.0000 | 12 | 35 |
| development | AB | known_issue_resolution | 0.9815 | 0.9907 | 0.0093 | 9 | 26 |
| development | AB | organization | 4.8194 | 4.8333 | 0.0139 | 12 | 35 |
| development | AB | unnecessary_change | 0.9167 | 0.8889 | -0.0278 | 12 | 35 |
| development | BC | requirement_failure_fraction | 0.0000 | 0.0000 | 0.0000 | 12 | 35 |
| development | BC | requirement_uncertainty_fraction | 0.0000 | 0.0000 | 0.0000 | 12 | 35 |
| development | BC | known_issue_resolution | 0.9722 | 0.9630 | -0.0093 | 9 | 27 |
| development | BC | organization | 4.8333 | 4.7917 | -0.0417 | 12 | 35 |
| development | BC | unnecessary_change | 0.9167 | 0.7778 | -0.1389 | 12 | 35 |
| holdout | AB | requirement_failure_fraction | 0.0000 | 0.0018 | 0.0018 | 17 | 31 |
| holdout | AB | requirement_uncertainty_fraction | 0.0000 | 0.0018 | 0.0018 | 17 | 31 |
| holdout | AB | known_issue_resolution | 0.9936 | 1.0000 | 0.0064 | 13 | 24 |
| holdout | AB | organization | 4.8725 | 4.9216 | 0.0490 | 17 | 31 |
| holdout | AB | unnecessary_change | 0.8627 | 0.9314 | 0.0686 | 17 | 31 |
| holdout | BC | requirement_failure_fraction | 0.0000 | 0.0000 | 0.0000 | 20 | 34 |
| holdout | BC | requirement_uncertainty_fraction | 0.0011 | 0.0000 | -0.0011 | 20 | 34 |
| holdout | BC | known_issue_resolution | 0.9917 | 0.9917 | 0.0000 | 15 | 24 |
| holdout | BC | organization | 4.8833 | 4.8917 | 0.0083 | 20 | 34 |
| holdout | BC | unnecessary_change | 0.8500 | 0.7000 | -0.1500 | 20 | 34 |

## Order consistency

planned: 54, eligible: 26, incomplete: 28, agreements: 16, disagreements: 10, decisive_reversals: 1.
Incomplete pairs have null agreement, not disagreement.

## Regression flags

Unique primary-assessed writer IDs per severity; repeated AB/BC assessments do not multiply writer counts.

| Split | Arm | Severity | Flagged/assessed writers | Flag occurrences |
| --- | --- | --- | --- | --- |
| development | A | critical | 0/35 | 0 |
| development | A | major | 0/35 | 0 |
| development | A | minor | 5/35 | 5 |
| development | B | critical | 0/36 | 0 |
| development | B | major | 0/36 | 0 |
| development | B | minor | 14/36 | 16 |
| development | C | critical | 0/35 | 0 |
| development | C | major | 0/35 | 0 |
| development | C | minor | 2/35 | 2 |
| holdout | A | critical | 0/31 | 0 |
| holdout | A | major | 0/31 | 0 |
| holdout | A | minor | 2/31 | 2 |
| holdout | B | critical | 0/50 | 0 |
| holdout | B | major | 0/50 | 0 |
| holdout | B | minor | 10/50 | 13 |
| holdout | C | critical | 0/34 | 0 |
| holdout | C | major | 0/34 | 0 |
| holdout | C | minor | 2/34 | 2 |

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
  "attempts": 99,
  "statuses": {
    "failed": 2,
    "valid": 88
  },
  "valid_coverage": {
    "numerator": 88,
    "denominator": 90,
    "rate": 0.9777777777777777
  },
  "first_attempt_validity": {
    "numerator": 81,
    "denominator": 90,
    "rate": 0.9
  },
  "retry_recovery": {
    "numerator": 7,
    "denominator": 9,
    "rate": 0.7777777777777778
  },
  "terminal": 90
}
```

| Token bucket | Sum | Known attempts | Unknown attempts |
| --- | --- | --- | --- |
| input | 1089 | 99 | 0 |
| output | 305302 | 99 | 0 |
| reasoning | 0 | 99 | 0 |
| cache_read | 0 | 99 | 0 |
| cache_write | 1234138 | 99 | 0 |
- seconds: 2564.544445786; known attempts 99, unknown 0.
- reported_cost: 6.140543000000003; known attempts 99, unknown 0.

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
  "attempts": 288,
  "statuses": {
    "failed": 97,
    "valid": 83
  },
  "valid_coverage": {
    "numerator": 83,
    "denominator": 180,
    "rate": 0.46111111111111114
  },
  "first_attempt_validity": {
    "numerator": 72,
    "denominator": 180,
    "rate": 0.4
  },
  "retry_recovery": {
    "numerator": 11,
    "denominator": 108,
    "rate": 0.10185185185185185
  },
  "terminal": 180
}
```

| Token bucket | Sum | Known attempts | Unknown attempts |
| --- | --- | --- | --- |
| input | 1265 | 288 | 0 |
| output | 389196 | 288 | 0 |
| reasoning | 0 | 288 | 0 |
| cache_read | 0 | 288 | 0 |
| cache_write | 1622076 | 288 | 0 |
- seconds: 3709.2529351200033; known attempts 288, unknown 0.
- reported_cost: 7.949679999999999; known attempts 288, unknown 0.

## Jobs without a selected valid result

| Role | Job | Split | Status | Terminal |
| --- | --- | --- | --- | --- |
| judges | blind-clean-dispatch-backlog-runbook-d2b6-r1-AB-primary | holdout | failed | True |
| judges | blind-clean-dispatch-backlog-runbook-d2b6-r2-AB-primary | holdout | failed | True |
| judges | blind-clean-dispatch-backlog-runbook-d2b6-r3-AB-primary | holdout | failed | True |
| judges | blind-clean-dispatch-backlog-runbook-d2b6-r3-AB-swap | holdout | failed | True |
| judges | blind-clean-generation-visibility-6e91-r1-BC-primary | development | failed | True |
| judges | blind-clean-indexer-release-8f3c-r1-AB-primary | holdout | failed | True |
| judges | blind-clean-indexer-release-8f3c-r1-BC-primary | holdout | failed | True |
| judges | blind-clean-indexer-release-8f3c-r2-AB-primary | holdout | failed | True |
| judges | blind-clean-indexer-release-8f3c-r3-AB-primary | holdout | failed | True |
| judges | blind-clean-indexer-release-8f3c-r3-BC-primary | holdout | failed | True |
| judges | blind-clean-lease-renewal-reference-c4a8-r1-AB-primary | holdout | failed | True |
| judges | blind-clean-lease-renewal-reference-c4a8-r2-AB-primary | holdout | failed | True |
| judges | blind-clean-lease-renewal-reference-c4a8-r2-AB-swap | holdout | failed | True |
| judges | blind-clean-lease-renewal-reference-c4a8-r2-BC-primary | holdout | failed | True |
| judges | blind-clean-recovery-window-note-a9e5-r1-BC-primary | holdout | failed | True |
| judges | blind-clean-recovery-window-note-a9e5-r1-BC-swap | holdout | failed | True |
| judges | blind-clean-recovery-window-note-a9e5-r2-AB-primary | holdout | failed | True |
| judges | blind-clean-recovery-window-note-a9e5-r2-BC-primary | holdout | failed | True |
| judges | blind-clean-recovery-window-note-a9e5-r3-AB-primary | holdout | failed | True |
| judges | blind-clean-recovery-window-note-a9e5-r3-BC-primary | holdout | failed | True |
| judges | blind-clean-recovery-window-note-a9e5-r3-BC-swap | holdout | failed | True |
| judges | blind-cons-contour-routing-decision-r2-AB-primary | holdout | failed | True |
| judges | blind-cons-contour-routing-decision-r2-AB-swap | holdout | failed | True |
| judges | blind-cons-contour-routing-decision-r3-AB-primary | holdout | failed | True |
| judges | blind-cons-contour-routing-decision-r3-AB-swap | holdout | failed | True |
| judges | blind-cons-contour-routing-decision-r3-BC-primary | holdout | failed | True |
| judges | blind-cons-harbor-spool-recovery-r2-AB-primary | holdout | failed | True |
| judges | blind-cons-harbor-spool-recovery-r3-AB-primary | holdout | failed | True |
| judges | blind-cons-harbor-spool-recovery-r3-BC-primary | holdout | failed | True |
| judges | blind-cons-northstar-cutover-bulletin-r1-AB-swap | holdout | failed | True |
| judges | blind-cons-northstar-cutover-bulletin-r1-BC-primary | holdout | failed | True |
| judges | blind-cons-northstar-cutover-bulletin-r3-AB-primary | holdout | failed | True |
| judges | blind-cons-northstar-cutover-bulletin-r3-BC-primary | holdout | failed | True |
| judges | blind-cons-solstice-field-dictionary-r1-AB-primary | holdout | failed | True |
| judges | blind-cons-solstice-field-dictionary-r1-BC-primary | holdout | failed | True |
| judges | blind-cons-solstice-field-dictionary-r2-BC-primary | holdout | failed | True |
| judges | blind-cons-solstice-field-dictionary-r3-AB-primary | holdout | failed | True |
| judges | blind-dup-badgewake-receipt-incident-r1-AB-primary | holdout | failed | True |
| judges | blind-dup-badgewake-receipt-incident-r2-AB-primary | holdout | failed | True |
| judges | blind-dup-badgewake-receipt-incident-r2-BC-primary | holdout | failed | True |
| judges | blind-dup-badgewake-receipt-incident-r2-BC-swap | holdout | failed | True |
| judges | blind-dup-badgewake-receipt-incident-r3-AB-primary | holdout | failed | True |
| judges | blind-dup-badgewake-receipt-incident-r3-BC-primary | holdout | failed | True |
| judges | blind-dup-badgewake-receipt-incident-r3-BC-swap | holdout | failed | True |
| judges | blind-dup-grantcoil-cursor-migration-r3-AB-primary | development | failed | True |
| judges | blind-dup-seatforge-hold-decision-r1-AB-primary | holdout | failed | True |
| judges | blind-dup-seatforge-hold-decision-r2-AB-primary | holdout | failed | True |
| judges | blind-dup-seatforge-hold-decision-r3-BC-primary | holdout | failed | True |
| judges | blind-dup-tilemint-terrain-quickstart-r3-BC-primary | holdout | failed | True |
| judges | blind-dup-voxhaven-archive-policy-r1-AB-primary | holdout | failed | True |
| judges | blind-dup-voxhaven-archive-policy-r1-AB-swap | holdout | failed | True |
| judges | blind-dup-voxhaven-archive-policy-r2-AB-primary | holdout | failed | True |
| judges | blind-dup-voxhaven-archive-policy-r2-BC-primary | holdout | failed | True |
| judges | blind-dup-voxhaven-archive-policy-r3-AB-primary | holdout | failed | True |
| judges | blind-org-aster-staged-promotion-r1-AB-primary | holdout | failed | True |
| judges | blind-org-aster-staged-promotion-r1-BC-swap | holdout | failed | True |
| judges | blind-org-aster-staged-promotion-r2-BC-primary | holdout | failed | True |
| judges | blind-org-brindle-job-endpoints-r1-AB-primary | holdout | failed | True |
| judges | blind-org-brindle-job-endpoints-r1-BC-primary | holdout | failed | True |
| judges | blind-org-brindle-job-endpoints-r2-AB-primary | holdout | failed | True |
| judges | blind-org-brindle-job-endpoints-r2-BC-primary | holdout | failed | True |
| judges | blind-org-brindle-job-endpoints-r3-AB-primary | holdout | failed | True |
| judges | blind-org-peregrine-render-options-r1-BC-primary | holdout | failed | True |
| judges | blind-org-peregrine-render-options-r2-BC-primary | holdout | failed | True |
| judges | blind-org-peregrine-render-options-r3-AB-swap | holdout | failed | True |
| judges | blind-org-velora-replica-recovery-r1-AB-primary | holdout | failed | True |
| judges | blind-org-velora-replica-recovery-r1-BC-primary | holdout | failed | True |
| judges | blind-org-velora-replica-recovery-r2-AB-primary | holdout | failed | True |
| judges | blind-org-velora-replica-recovery-r2-BC-swap | holdout | failed | True |
| judges | blind-org-velora-replica-recovery-r3-AB-primary | holdout | failed | True |
| judges | blind-org-velora-replica-recovery-r3-BC-primary | holdout | failed | True |
| judges | blind-rep-bellweather-loan-procedures-r1-BC-primary | holdout | failed | True |
| judges | blind-rep-bellweather-loan-procedures-r2-BC-primary | holdout | failed | True |
| judges | blind-rep-bellweather-loan-procedures-r3-AB-primary | holdout | failed | True |
| judges | blind-rep-bellweather-loan-procedures-r3-BC-primary | holdout | failed | True |
| judges | blind-rep-cedarbench-recovery-reference-r2-AB-swap | holdout | failed | True |
| judges | blind-rep-cedarbench-recovery-reference-r2-BC-primary | holdout | failed | True |
| judges | blind-rep-cedarbench-recovery-reference-r3-AB-primary | holdout | failed | True |
| judges | blind-rep-northbank-relocation-notices-r3-AB-primary | holdout | failed | True |
| judges | blind-rep-pulsebox-platform-tabs-r1-BC-primary | holdout | failed | True |
| judges | blind-rep-pulsebox-platform-tabs-r2-AB-swap | holdout | failed | True |
| judges | blind-tech-anchorvault-restore-faq-rb26-r1-AB-primary | holdout | failed | True |
| judges | blind-tech-anchorvault-restore-faq-rb26-r1-BC-primary | holdout | failed | True |
| judges | blind-tech-anchorvault-restore-faq-rb26-r2-AB-primary | holdout | failed | True |
| judges | blind-tech-anchorvault-restore-faq-rb26-r2-BC-primary | holdout | failed | True |
| judges | blind-tech-cobaltkey-cutover-advisory-rb26-r1-AB-primary | holdout | failed | True |
| judges | blind-tech-cobaltkey-cutover-advisory-rb26-r2-AB-swap | holdout | failed | True |
| judges | blind-tech-cobaltkey-cutover-advisory-rb26-r2-BC-primary | holdout | failed | True |
| judges | blind-tech-cobaltkey-cutover-advisory-rb26-r3-AB-swap | holdout | failed | True |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r1-AB-primary | holdout | failed | True |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r1-BC-primary | holdout | failed | True |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r2-AB-primary | holdout | failed | True |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r2-BC-primary | holdout | failed | True |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r3-AB-primary | holdout | failed | True |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r3-BC-primary | holdout | failed | True |
| judges | blind-tech-prismtrace-window-reference-rb26-r1-BC-primary | holdout | failed | True |
| judges | blind-tech-prismtrace-window-reference-rb26-r2-AB-swap | holdout | failed | True |
| judges | blind-tech-prismtrace-window-reference-rb26-r2-BC-primary | holdout | failed | True |
| judges | blind-tech-prismtrace-window-reference-rb26-r3-BC-primary | holdout | failed | True |

## Validator/transport failures

| Role | Job | Attempt | Classification |
| --- | --- | --- | --- |
| writers | blind-tech-cobaltkey-cutover-advisory-rb26-r2-B | 1 | transport |
| judges | blind-clean-dispatch-backlog-runbook-d2b6-r1-AB-primary | 1 | transport |
| judges | blind-clean-dispatch-backlog-runbook-d2b6-r1-AB-primary | 2 | transport |
| judges | blind-clean-dispatch-backlog-runbook-d2b6-r2-AB-primary | 1 | transport |
| judges | blind-clean-dispatch-backlog-runbook-d2b6-r2-AB-primary | 2 | transport |
| judges | blind-clean-dispatch-backlog-runbook-d2b6-r2-BC-primary | 1 | schema_or_evidence |
| judges | blind-clean-dispatch-backlog-runbook-d2b6-r3-AB-primary | 1 | transport |
| judges | blind-clean-dispatch-backlog-runbook-d2b6-r3-AB-primary | 2 | transport |
| judges | blind-clean-dispatch-backlog-runbook-d2b6-r3-AB-swap | 1 | transport |
| judges | blind-clean-dispatch-backlog-runbook-d2b6-r3-AB-swap | 2 | transport |
| judges | blind-clean-generation-visibility-6e91-r1-BC-primary | 1 | schema_or_evidence |
| judges | blind-clean-generation-visibility-6e91-r1-BC-primary | 2 | schema_or_evidence |
| judges | blind-clean-generation-visibility-6e91-r3-BC-primary | 1 | schema_or_evidence |
| judges | blind-clean-indexer-release-8f3c-r1-AB-primary | 1 | schema_or_evidence |
| judges | blind-clean-indexer-release-8f3c-r1-AB-primary | 2 | transport |
| judges | blind-clean-indexer-release-8f3c-r1-BC-primary | 1 | transport |
| judges | blind-clean-indexer-release-8f3c-r1-BC-primary | 2 | transport |
| judges | blind-clean-indexer-release-8f3c-r2-AB-primary | 1 | transport |
| judges | blind-clean-indexer-release-8f3c-r2-AB-primary | 2 | transport |
| judges | blind-clean-indexer-release-8f3c-r3-AB-primary | 1 | schema_or_evidence |
| judges | blind-clean-indexer-release-8f3c-r3-AB-primary | 2 | schema_or_evidence |
| judges | blind-clean-indexer-release-8f3c-r3-BC-primary | 1 | transport |
| judges | blind-clean-indexer-release-8f3c-r3-BC-primary | 2 | transport |
| judges | blind-clean-lease-renewal-reference-c4a8-r1-AB-primary | 1 | transport |
| judges | blind-clean-lease-renewal-reference-c4a8-r1-AB-primary | 2 | transport |
| judges | blind-clean-lease-renewal-reference-c4a8-r2-AB-primary | 1 | transport |
| judges | blind-clean-lease-renewal-reference-c4a8-r2-AB-primary | 2 | transport |
| judges | blind-clean-lease-renewal-reference-c4a8-r2-AB-swap | 1 | transport |
| judges | blind-clean-lease-renewal-reference-c4a8-r2-AB-swap | 2 | transport |
| judges | blind-clean-lease-renewal-reference-c4a8-r2-BC-primary | 1 | transport |
| judges | blind-clean-lease-renewal-reference-c4a8-r2-BC-primary | 2 | transport |
| judges | blind-clean-recovery-window-note-a9e5-r1-BC-primary | 1 | transport |
| judges | blind-clean-recovery-window-note-a9e5-r1-BC-primary | 2 | transport |
| judges | blind-clean-recovery-window-note-a9e5-r1-BC-swap | 1 | transport |
| judges | blind-clean-recovery-window-note-a9e5-r1-BC-swap | 2 | transport |
| judges | blind-clean-recovery-window-note-a9e5-r2-AB-primary | 1 | transport |
| judges | blind-clean-recovery-window-note-a9e5-r2-AB-primary | 2 | transport |
| judges | blind-clean-recovery-window-note-a9e5-r2-BC-primary | 1 | transport |
| judges | blind-clean-recovery-window-note-a9e5-r2-BC-primary | 2 | transport |
| judges | blind-clean-recovery-window-note-a9e5-r3-AB-primary | 1 | transport |
| judges | blind-clean-recovery-window-note-a9e5-r3-AB-primary | 2 | transport |
| judges | blind-clean-recovery-window-note-a9e5-r3-BC-primary | 1 | transport |
| judges | blind-clean-recovery-window-note-a9e5-r3-BC-primary | 2 | transport |
| judges | blind-clean-recovery-window-note-a9e5-r3-BC-swap | 1 | transport |
| judges | blind-clean-recovery-window-note-a9e5-r3-BC-swap | 2 | transport |
| judges | blind-clean-sandbox-first-delivery-b7d2-r3-AB-primary | 1 | schema_or_evidence |
| judges | blind-cons-cedarline-command-reference-r2-BC-primary | 1 | schema_or_evidence |
| judges | blind-cons-contour-routing-decision-r2-AB-primary | 1 | transport |
| judges | blind-cons-contour-routing-decision-r2-AB-primary | 2 | transport |
| judges | blind-cons-contour-routing-decision-r2-AB-swap | 1 | transport |
| judges | blind-cons-contour-routing-decision-r2-AB-swap | 2 | transport |
| judges | blind-cons-contour-routing-decision-r3-AB-primary | 1 | transport |
| judges | blind-cons-contour-routing-decision-r3-AB-primary | 2 | transport |
| judges | blind-cons-contour-routing-decision-r3-AB-swap | 1 | transport |
| judges | blind-cons-contour-routing-decision-r3-AB-swap | 2 | transport |
| judges | blind-cons-contour-routing-decision-r3-BC-primary | 1 | transport |
| judges | blind-cons-contour-routing-decision-r3-BC-primary | 2 | transport |
| judges | blind-cons-finchpipe-first-event-r3-BC-primary | 1 | schema_or_evidence |
| judges | blind-cons-harbor-spool-recovery-r2-AB-primary | 1 | transport |
| judges | blind-cons-harbor-spool-recovery-r2-AB-primary | 2 | transport |
| judges | blind-cons-harbor-spool-recovery-r3-AB-primary | 1 | transport |
| judges | blind-cons-harbor-spool-recovery-r3-AB-primary | 2 | transport |
| judges | blind-cons-harbor-spool-recovery-r3-AB-swap | 1 | schema_or_evidence |
| judges | blind-cons-harbor-spool-recovery-r3-BC-primary | 1 | transport |
| judges | blind-cons-harbor-spool-recovery-r3-BC-primary | 2 | transport |
| judges | blind-cons-northstar-cutover-bulletin-r1-AB-swap | 1 | transport |
| judges | blind-cons-northstar-cutover-bulletin-r1-AB-swap | 2 | transport |
| judges | blind-cons-northstar-cutover-bulletin-r1-BC-primary | 1 | transport |
| judges | blind-cons-northstar-cutover-bulletin-r1-BC-primary | 2 | transport |
| judges | blind-cons-northstar-cutover-bulletin-r3-AB-primary | 1 | schema_or_evidence |
| judges | blind-cons-northstar-cutover-bulletin-r3-AB-primary | 2 | schema_or_evidence |
| judges | blind-cons-northstar-cutover-bulletin-r3-BC-primary | 1 | transport |
| judges | blind-cons-northstar-cutover-bulletin-r3-BC-primary | 2 | transport |
| judges | blind-cons-solstice-field-dictionary-r1-AB-primary | 1 | transport |
| judges | blind-cons-solstice-field-dictionary-r1-AB-primary | 2 | transport |
| judges | blind-cons-solstice-field-dictionary-r1-BC-primary | 1 | transport |
| judges | blind-cons-solstice-field-dictionary-r1-BC-primary | 2 | transport |
| judges | blind-cons-solstice-field-dictionary-r2-BC-primary | 1 | transport |
| judges | blind-cons-solstice-field-dictionary-r2-BC-primary | 2 | transport |
| judges | blind-cons-solstice-field-dictionary-r3-AB-primary | 1 | transport |
| judges | blind-cons-solstice-field-dictionary-r3-AB-primary | 2 | transport |
| judges | blind-dup-badgewake-receipt-incident-r1-AB-primary | 1 | transport |
| judges | blind-dup-badgewake-receipt-incident-r1-AB-primary | 2 | transport |
| judges | blind-dup-badgewake-receipt-incident-r2-AB-primary | 1 | transport |
| judges | blind-dup-badgewake-receipt-incident-r2-AB-primary | 2 | transport |
| judges | blind-dup-badgewake-receipt-incident-r2-BC-primary | 1 | transport |
| judges | blind-dup-badgewake-receipt-incident-r2-BC-primary | 2 | transport |
| judges | blind-dup-badgewake-receipt-incident-r2-BC-swap | 1 | transport |
| judges | blind-dup-badgewake-receipt-incident-r2-BC-swap | 2 | transport |
| judges | blind-dup-badgewake-receipt-incident-r3-AB-primary | 1 | transport |
| judges | blind-dup-badgewake-receipt-incident-r3-AB-primary | 2 | transport |
| judges | blind-dup-badgewake-receipt-incident-r3-BC-primary | 1 | transport |
| judges | blind-dup-badgewake-receipt-incident-r3-BC-primary | 2 | transport |
| judges | blind-dup-badgewake-receipt-incident-r3-BC-swap | 1 | transport |
| judges | blind-dup-badgewake-receipt-incident-r3-BC-swap | 2 | transport |
| judges | blind-dup-grantcoil-cursor-migration-r1-BC-swap | 1 | schema_or_evidence |
| judges | blind-dup-grantcoil-cursor-migration-r3-AB-primary | 1 | schema_or_evidence |
| judges | blind-dup-grantcoil-cursor-migration-r3-AB-primary | 2 | schema_or_evidence |
| judges | blind-dup-seatforge-hold-decision-r1-AB-primary | 1 | transport |
| judges | blind-dup-seatforge-hold-decision-r1-AB-primary | 2 | transport |
| judges | blind-dup-seatforge-hold-decision-r2-AB-primary | 1 | transport |
| judges | blind-dup-seatforge-hold-decision-r2-AB-primary | 2 | transport |
| judges | blind-dup-seatforge-hold-decision-r3-AB-primary | 1 | schema_or_evidence |
| judges | blind-dup-seatforge-hold-decision-r3-BC-primary | 1 | transport |
| judges | blind-dup-seatforge-hold-decision-r3-BC-primary | 2 | transport |
| judges | blind-dup-tilemint-terrain-quickstart-r1-BC-primary | 1 | schema_or_evidence |
| judges | blind-dup-tilemint-terrain-quickstart-r3-BC-primary | 1 | transport |
| judges | blind-dup-tilemint-terrain-quickstart-r3-BC-primary | 2 | transport |
| judges | blind-dup-voxhaven-archive-policy-r1-AB-primary | 1 | transport |
| judges | blind-dup-voxhaven-archive-policy-r1-AB-primary | 2 | transport |
| judges | blind-dup-voxhaven-archive-policy-r1-AB-swap | 1 | transport |
| judges | blind-dup-voxhaven-archive-policy-r1-AB-swap | 2 | transport |
| judges | blind-dup-voxhaven-archive-policy-r1-BC-primary | 1 | schema_or_evidence |
| judges | blind-dup-voxhaven-archive-policy-r2-AB-primary | 1 | transport |
| judges | blind-dup-voxhaven-archive-policy-r2-AB-primary | 2 | transport |
| judges | blind-dup-voxhaven-archive-policy-r2-BC-primary | 1 | transport |
| judges | blind-dup-voxhaven-archive-policy-r2-BC-primary | 2 | transport |
| judges | blind-dup-voxhaven-archive-policy-r3-AB-primary | 1 | schema_or_evidence |
| judges | blind-dup-voxhaven-archive-policy-r3-AB-primary | 2 | schema_or_evidence |
| judges | blind-org-aster-staged-promotion-r1-AB-primary | 1 | transport |
| judges | blind-org-aster-staged-promotion-r1-AB-primary | 2 | transport |
| judges | blind-org-aster-staged-promotion-r1-BC-swap | 1 | transport |
| judges | blind-org-aster-staged-promotion-r1-BC-swap | 2 | transport |
| judges | blind-org-aster-staged-promotion-r2-BC-primary | 1 | transport |
| judges | blind-org-aster-staged-promotion-r2-BC-primary | 2 | transport |
| judges | blind-org-brindle-job-endpoints-r1-AB-primary | 1 | transport |
| judges | blind-org-brindle-job-endpoints-r1-AB-primary | 2 | transport |
| judges | blind-org-brindle-job-endpoints-r1-BC-primary | 1 | transport |
| judges | blind-org-brindle-job-endpoints-r1-BC-primary | 2 | transport |
| judges | blind-org-brindle-job-endpoints-r2-AB-primary | 1 | transport |
| judges | blind-org-brindle-job-endpoints-r2-AB-primary | 2 | transport |
| judges | blind-org-brindle-job-endpoints-r2-BC-primary | 1 | schema_or_evidence |
| judges | blind-org-brindle-job-endpoints-r2-BC-primary | 2 | schema_or_evidence |
| judges | blind-org-brindle-job-endpoints-r3-AB-primary | 1 | transport |
| judges | blind-org-brindle-job-endpoints-r3-AB-primary | 2 | transport |
| judges | blind-org-ledgerwake-cursor-lifecycle-r1-BC-primary | 1 | schema_or_evidence |
| judges | blind-org-peregrine-render-options-r1-BC-primary | 1 | transport |
| judges | blind-org-peregrine-render-options-r1-BC-primary | 2 | transport |
| judges | blind-org-peregrine-render-options-r2-BC-primary | 1 | transport |
| judges | blind-org-peregrine-render-options-r2-BC-primary | 2 | transport |
| judges | blind-org-peregrine-render-options-r3-AB-swap | 1 | transport |
| judges | blind-org-peregrine-render-options-r3-AB-swap | 2 | transport |
| judges | blind-org-tern-relay-commissioning-r2-BC-swap | 1 | schema_or_evidence |
| judges | blind-org-velora-replica-recovery-r1-AB-primary | 1 | transport |
| judges | blind-org-velora-replica-recovery-r1-AB-primary | 2 | transport |
| judges | blind-org-velora-replica-recovery-r1-BC-primary | 1 | schema_or_evidence |
| judges | blind-org-velora-replica-recovery-r1-BC-primary | 2 | schema_or_evidence |
| judges | blind-org-velora-replica-recovery-r2-AB-primary | 1 | transport |
| judges | blind-org-velora-replica-recovery-r2-AB-primary | 2 | transport |
| judges | blind-org-velora-replica-recovery-r2-BC-swap | 1 | transport |
| judges | blind-org-velora-replica-recovery-r2-BC-swap | 2 | transport |
| judges | blind-org-velora-replica-recovery-r3-AB-primary | 1 | schema_or_evidence |
| judges | blind-org-velora-replica-recovery-r3-AB-primary | 2 | schema_or_evidence |
| judges | blind-org-velora-replica-recovery-r3-BC-primary | 1 | schema_or_evidence |
| judges | blind-org-velora-replica-recovery-r3-BC-primary | 2 | schema_or_evidence |
| judges | blind-rep-bellweather-loan-procedures-r1-BC-primary | 1 | transport |
| judges | blind-rep-bellweather-loan-procedures-r1-BC-primary | 2 | transport |
| judges | blind-rep-bellweather-loan-procedures-r2-BC-primary | 1 | transport |
| judges | blind-rep-bellweather-loan-procedures-r2-BC-primary | 2 | transport |
| judges | blind-rep-bellweather-loan-procedures-r3-AB-primary | 1 | transport |
| judges | blind-rep-bellweather-loan-procedures-r3-AB-primary | 2 | transport |
| judges | blind-rep-bellweather-loan-procedures-r3-BC-primary | 1 | transport |
| judges | blind-rep-bellweather-loan-procedures-r3-BC-primary | 2 | transport |
| judges | blind-rep-cedarbench-recovery-reference-r2-AB-swap | 1 | transport |
| judges | blind-rep-cedarbench-recovery-reference-r2-AB-swap | 2 | transport |
| judges | blind-rep-cedarbench-recovery-reference-r2-BC-primary | 1 | transport |
| judges | blind-rep-cedarbench-recovery-reference-r2-BC-primary | 2 | transport |
| judges | blind-rep-cedarbench-recovery-reference-r3-AB-primary | 1 | transport |
| judges | blind-rep-cedarbench-recovery-reference-r3-AB-primary | 2 | transport |
| judges | blind-rep-northbank-relocation-notices-r2-BC-primary | 1 | schema_or_evidence |
| judges | blind-rep-northbank-relocation-notices-r3-AB-primary | 1 | transport |
| judges | blind-rep-northbank-relocation-notices-r3-AB-primary | 2 | transport |
| judges | blind-rep-pulsebox-platform-tabs-r1-BC-primary | 1 | transport |
| judges | blind-rep-pulsebox-platform-tabs-r1-BC-primary | 2 | transport |
| judges | blind-rep-pulsebox-platform-tabs-r2-AB-swap | 1 | transport |
| judges | blind-rep-pulsebox-platform-tabs-r2-AB-swap | 2 | transport |
| judges | blind-tech-anchorvault-restore-faq-rb26-r1-AB-primary | 1 | transport |
| judges | blind-tech-anchorvault-restore-faq-rb26-r1-AB-primary | 2 | transport |
| judges | blind-tech-anchorvault-restore-faq-rb26-r1-BC-primary | 1 | transport |
| judges | blind-tech-anchorvault-restore-faq-rb26-r1-BC-primary | 2 | transport |
| judges | blind-tech-anchorvault-restore-faq-rb26-r2-AB-primary | 1 | transport |
| judges | blind-tech-anchorvault-restore-faq-rb26-r2-AB-primary | 2 | transport |
| judges | blind-tech-anchorvault-restore-faq-rb26-r2-BC-primary | 1 | transport |
| judges | blind-tech-anchorvault-restore-faq-rb26-r2-BC-primary | 2 | transport |
| judges | blind-tech-cobaltkey-cutover-advisory-rb26-r1-AB-primary | 1 | transport |
| judges | blind-tech-cobaltkey-cutover-advisory-rb26-r1-AB-primary | 2 | transport |
| judges | blind-tech-cobaltkey-cutover-advisory-rb26-r2-AB-primary | 1 | schema_or_evidence |
| judges | blind-tech-cobaltkey-cutover-advisory-rb26-r2-AB-swap | 1 | transport |
| judges | blind-tech-cobaltkey-cutover-advisory-rb26-r2-AB-swap | 2 | transport |
| judges | blind-tech-cobaltkey-cutover-advisory-rb26-r2-BC-primary | 1 | transport |
| judges | blind-tech-cobaltkey-cutover-advisory-rb26-r2-BC-primary | 2 | transport |
| judges | blind-tech-cobaltkey-cutover-advisory-rb26-r3-AB-swap | 1 | schema_or_evidence |
| judges | blind-tech-cobaltkey-cutover-advisory-rb26-r3-AB-swap | 2 | schema_or_evidence |
| judges | blind-tech-cobaltkey-cutover-advisory-rb26-r3-BC-primary | 1 | schema_or_evidence |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r1-AB-primary | 1 | transport |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r1-AB-primary | 2 | transport |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r1-AB-swap | 1 | schema_or_evidence |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r1-BC-primary | 1 | schema_or_evidence |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r1-BC-primary | 2 | schema_or_evidence |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r2-AB-primary | 1 | transport |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r2-AB-primary | 2 | transport |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r2-BC-primary | 1 | transport |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r2-BC-primary | 2 | transport |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r3-AB-primary | 1 | transport |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r3-AB-primary | 2 | transport |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r3-BC-primary | 1 | transport |
| judges | blind-tech-petalgrid-ingest-contract-rb26-r3-BC-primary | 2 | transport |
| judges | blind-tech-prismtrace-window-reference-rb26-r1-BC-primary | 1 | transport |
| judges | blind-tech-prismtrace-window-reference-rb26-r1-BC-primary | 2 | transport |
| judges | blind-tech-prismtrace-window-reference-rb26-r2-AB-primary | 1 | schema_or_evidence |
| judges | blind-tech-prismtrace-window-reference-rb26-r2-AB-swap | 1 | schema_or_evidence |
| judges | blind-tech-prismtrace-window-reference-rb26-r2-AB-swap | 2 | schema_or_evidence |
| judges | blind-tech-prismtrace-window-reference-rb26-r2-BC-primary | 1 | transport |
| judges | blind-tech-prismtrace-window-reference-rb26-r2-BC-primary | 2 | transport |
| judges | blind-tech-prismtrace-window-reference-rb26-r3-AB-primary | 1 | schema_or_evidence |
| judges | blind-tech-prismtrace-window-reference-rb26-r3-BC-primary | 1 | transport |
| judges | blind-tech-prismtrace-window-reference-rb26-r3-BC-primary | 2 | transport |

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
