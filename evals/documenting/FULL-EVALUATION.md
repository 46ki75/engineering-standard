# Full fixed-draft evaluation

Execution is complete. A provider failure required a separate, consistently rejudged GPT-5.5 pass; see the [recovery record](RECOVERY.md) and [final report](results/full-openai55-v1/report.md). The design and criteria below were recorded before full-suite inference.

The user approved proceeding under their fixed-rate subscriptions. Usage remains recorded for reproducibility; it is not an execution approval gate.

## Frozen design

Use the 36 fixtures in `cases/full-blind/`: six categories, each with two development cases and four held-out cases. Every case has a distinct underlying template group. Revisions use the same A/B/C prompts as the initial calibration:

- A: original engineering guidelines without the documentation-review bullet.
- B: guidelines with the short documentation-review rule.
- C: B plus the candidate reference's procedure and examples.

Each case receives three independent revisions per arm: **324 writer jobs**. Pair A/B and B/C in each repetition, randomizing presentation order: **216 primary judge jobs**. A seeded, category-and-split-stratified 25% sample is judged again in reverse order: **54 swaps**, for **270 judge jobs** total.

Writers use `openai/gpt-6-astra` with `high` reasoning. Judges use `github-copilot/claude-sonnet-5` with `high` reasoning. Both run in fresh isolated OpenCode sessions. Writers have no tools; judges can use only the virtual `StructuredOutput` response tool. Local validation checks structure, IDs, values, and exact candidate quotations. The response tool guides generation; local validation is still necessary.

A job may receive at most two attempts. Retry only transport or structurally invalid responses, never an unfavorable semantic assessment. Preserve all attempts and first-attempt reliability; select the first valid result. Run development jobs before held-out jobs. The reference remains frozen throughout both phases.

## Judge calibration

`omission-controls-v2` tests six omitted facts in both orders. All 12 responses were valid, identified the omitted fact, passed its preserved counterpart, and preferred the preserved document. All 360 untouched-atom assessments passed. This establishes sensitivity on these controls, not perfect judging on arbitrary documents.

The first control run retained six failures: five caused by an unnecessary maximum length on the final comparison explanation, and one by a JSON object encoded as a string. The second protocol removes that arbitrary explanation cap and explicitly requires object-valued fields. Both runs remain recorded.

## Predeclared analysis and decision

The primary comparison is C versus B on the 24 held-out documents. Score C wins as +1, B wins as -1, and ties/uncertainty as 0, reporting the latter separately. Average valid primary repetitions within each document, then weight documents equally. Exclude swaps from the primary estimate.

Compute a 95% percentile bootstrap interval by resampling documents within each category, with 10,000 resamples and seed 46075. Repetitions and swapped judgments are dependent observations, not additional documents. Report development outcomes separately; A/B is a secondary comparison.

Secondary measures are paired atomic requirement-failure fractions, known-issue resolution (`resolved=1`, `partial=0.5`, other statuses `0`), organization, unnecessary change, regression flags, word counts, and operational reliability. For paired measures, compare the two assessments from the same primary judgment rather than pooling B's appearances across both comparisons.

Adopt C only if:

1. Its primary interval's lower bound exceeds zero.
2. Its paired requirement-failure fraction does not increase.
3. No newly introduced critical regression is confirmed.
4. At least 90% of primary B/C judgments are valid and every held-out document has at least two valid repetitions.

Otherwise retain B. These conservative criteria select evidence-supported complexity, not a universal winner. Review critical flags and substantive disputes against the source facts; preserve the original assessments and label any secondary AI-assisted adjudication.

## Fixture provenance

An earlier batch in `cases/full/` was excluded before any full-suite inference: several authors received unintended candidate/calibration excerpts from a file-scoped search. Replacement authors for `cases/full-blind/` could read only the two applicable `AGENTS.md` files and their own newly created fixtures. They did not read candidate prompts or results. A separate validation inspected all 36 replacements for internal ground-truth consistency. It corrected one clean fixture's incomplete standalone table before freezing the suite.

The held-out set is isolated from prompt development, but remains synthetic and AI-authored. Model pretraining contamination cannot be ruled out in general. This experiment tests supplied-draft finalization; it does not test initial generation, normal coding-agent behavior, research, or skill/reference discovery.

## Commands

```sh
python3 -B evals/documenting/full.py validate
python3 -B evals/documenting/full.py init --output evals/documenting/results/full-v1
python3 -B evals/documenting/full.py writers --output evals/documenting/results/full-v1 --split development --concurrency 6
python3 -B evals/documenting/full.py judges --output evals/documenting/results/full-v1 --split development --concurrency 6
python3 -B evals/documenting/full.py writers --output evals/documenting/results/full-v1 --split holdout --concurrency 6
python3 -B evals/documenting/full.py judges --output evals/documenting/results/full-v1 --split holdout --concurrency 6
python3 -B evals/documenting/full.py summarize --output evals/documenting/results/full-v1
```

`--limit` bounds a command's number of jobs. Repeating a command resumes unfinished jobs while preserving the frozen attempt limit. Each invocation records concurrency and duration. Inspect status without making model calls using `full.py status`.
