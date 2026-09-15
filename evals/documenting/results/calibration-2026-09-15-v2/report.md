# Documentation-review calibration: September 15, 2026

## Decision

The host-based loop works, but the judging protocol needs improvement before the comprehensive evaluation. This calibration does **not demonstrate an advantage for the detailed reference over the short rule**. It also exposes a completeness-checking blind spot shared by the writer and judge.

The candidate remains in [the documentation reference](../../../../skills/engineering-standard/references/documenting/README.md). Calibration does not justify adopting it as required guidance.

## Experiment and integrity

- **A:** original engineering guidelines without the documentation-review rule.
- **B:** the current guidelines, including the short rule.
- **C:** B plus the candidate's review procedure and examples.
- Three fixed drafts, one revision per arm: **9 writer sessions** on `openai/gpt-6-astra`, requested `high` reasoning.
- A/B and B/C comparisons in both orders: **12 judge sessions** on `github-copilot/claude-sonnet-5`, provider-default reasoning.
- OpenCode 1.18.31; fresh custom agents with disabled tools, isolated home/config/state, and existing authentication. No containers.

All 21 model sessions finished normally. Nine writer outputs passed the response checks; **10 of 12 judge outputs passed the strict JSON contract**. The two schema failures remain failures and are excluded from votes. Their usage is included.

[The integrity audit](audit.json) independently verified all 21 exported user messages against their recorded inputs, model/provider/agent metadata, unique sessions, hashes, and absence of tool calls. Integrity passing is separate from response validity. The writer's exposed `high` variant matched; no judge variant was exposed. The archived custom prompts are not a capture of every provider-side system transformation.

The runner's **46 offline tests passed**. An initial preflight implementation incorrectly rejected overridden default permission entries. That check was fixed to inspect resolved tool availability before any model call; the earlier diagnostic artifacts remain in `../calibration-2026-09-15/`.

## Findings

### Similar defect correction across the arms

All three arms corrected the API timeout contradiction. All three removed the runbook's exact/paraphrased duplication and moved its prerequisites before mutation. This gives **12 resolved output–issue pairs**: four known issues across three arms.

All nine outputs passed all applicable mechanical checks: **77/77** in total. Those checks verify literals and syntax, not semantic completeness.

On the clean document, B and C preserved the original text apart from its final newline and were byte-identical to each other. A made small, meaning-preserving wording changes. The judges' claim that B/C were byte-identical to the original was slightly inaccurate; the newline difference is established by direct comparison.

### The judge missed the same omission in all three API outputs

The original explains that `template_id` selects the stored layout and `record_id` selects the data rendered into it. All three revisions retain the field names and example values but remove those explanations. The supplied requirement `R-MICA-REQUEST-CONTRACT` explicitly requires their distinct meanings.

Secondary AI-assisted inspection, with arm labels visible, therefore marks that requirement as failed in A, B, and C. This is **3 omissions among 81 unique output–requirement pairs**, not a comparative advantage for any arm. Under the fixture's annotation the requirement is major; the operational impact is less certain because the names remain suggestive and the revisions do not prescribe incorrect request behavior.

The valid judges nevertheless passed all **180 requirement assessments**. These are repeated assessments of 81 unique output–requirement pairs, not 180 independent observations. Six repeated pass assessments missed the three omissions. See the [adjudication record](adjudication.json) for evidence.

### Ordering and regression judgments need calibration

All six valid B/C judgments were ties. Of four comparisons with valid judgments in both orders, three agreed and one changed from a tie to A winning. Two additional comparisons lack one valid order; these are missing comparisons, not observed positional disagreements.

Two minor regression flags concerned Quarry B:

1. A thinner handoff was alleged by comparing B with A, rather than with the original. B retained the required evidence capture. This is not an established original-to-revision regression.
2. B routes observation failure/missing metrics into the existing containment procedure. That is a reasonable inference from failed acceptance, although the source does not specify the observation-error case separately. A contains a similar branch. Treat this as a sourcing qualification, not a confirmed substantive regression.

These are secondary, unblinded adjudications. Raw judge assessments remain unchanged.

### Two structured-response failures

| Trial | Contract violation |
| --- | --- |
| Fallow BA | `winner` was placed inside `candidates`, leaving the required root field absent. |
| Mica AB | `candidates` contained an extra `organization_note` key. |

Both responses were parseable JSON; neither satisfied the required schema. No normalization, replacement vote, or automatic retry was applied.

## Measured usage

Counts cover experimental sessions only, excluding authoring, diagnostics, and secondary analysis. Token buckets follow OpenCode's normalization: input, visible output, reasoning, cache reads, and cache writes are added once each.

| Measure | Writers | Judges |
| --- | ---: | ---: |
| Sessions | 9 | 12 |
| Valid responses | 9 | 10 |
| Reported tokens, all buckets | 26,663 | 137,015 |
| Mean duration including CLI startup | 32.6 s | 18.0 s |
| Sum of session durations | 293.7 s | 215.9 s |
| OpenCode-reported cost | $0.00 | $0.514448 |

Total: **163,678 reported tokens**. The writer uses OAuth; its zero reported cost does not establish free usage or quantify subscription/quota consumption. Actual billing has not been verified. CLI-internal retries and interrupted-attempt usage are not fully exposed, so 21 completed model steps is not a verified count of all provider attempts.

## Full-suite estimate and next gate

The proposed suite remains **36 drafts × 3 arms × 3 repetitions = 324 writers**, plus **270 judges**: 216 A/B and B/C comparisons and 54 prespecified order swaps. Use 12 development cases and 24 held-out cases, separated by underlying document/template family.

Scaling the observed averages to those **594 sessions** gives:

- Approximately **4.04 million reported tokens**: 0.96 million writer and 3.08 million judge tokens.
- Approximately **4.29 serial hours**, or **86 minutes under ideal three-way concurrency**. A practical planning allowance is **2–3 hours of model execution**, excluding fixture construction and substantive adjudication.
- Approximately **$11.58 in judge-reported cost**, plus writer subscription/quota usage that this telemetry cannot price.

These are rough extrapolations from 472–727-word drafts. Longer cases, reliability changes, retries, provider limits, and additional development iterations can increase usage. This is not a total billing quote or a guaranteed wall-clock duration.

Before scaling:

1. Make judge output structurally reliable, preferably with enforced structured output; preserve and account for any failed attempts.
2. Split compound completeness requirements into atomic facts and verify judge sensitivity using deliberately omitted facts. Preserve unchanged good documents as controls.
3. Add varied documents and task scopes; keep the candidate frozen during held-out testing. The easy baseline successes here do not establish that the rule is unnecessary or effective elsewhere.
4. Confirm the full-suite usage budget after reviewing this calibration, as selected by the user.

## Reproduce the analysis

From the repository root:

```sh
python3 -m unittest discover -s evals/documenting/tests -v
python3 evals/documenting/run.py summarize --output evals/documenting/results/calibration-2026-09-15-v2
python3 evals/documenting/analyze.py --output evals/documenting/results/calibration-2026-09-15-v2
python3 evals/documenting/audit.py --output evals/documenting/results/calibration-2026-09-15-v2
```

These commands do not make model calls. The audit reads existing OpenCode session exports; it requires the local session store. `summary.json` and `analysis.json` are computed results. `adjudication.json` records the separate qualitative assessment; it is not an automatic or human ground-truth label set.
