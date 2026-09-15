# Judge recovery record

The objective remains the frozen fixed-draft documentation field test: determine whether the candidate reference (C) improves on the short rule (B). Provider availability required a judge-protocol change. **The replacement run is complete: 269/270 judging jobs are valid.** See the [final report](results/full-openai55-v1/report.md) for the decision and limitations.

## Original run and replacement selection

In `full-v1`, all **324** `openai/gpt-6-astra` high writer outputs completed in **325 attempts**, including one transport retry. The original `github-copilot/claude-sonnet-5` high run retained **171/270 valid jobs**. During execution, **173 HTTP 402 attempts** affected **87 holdout jobs**, all reporting `isRetryable: false`. The original run remains incomplete, with its attempts and partial reports. No extra paid credits were purchased or provider configuration changed to continue it.

Replacement selection used calibration only:

- `openai/gpt-5.6-luna` high: **6/12 valid control responses**, with five schema failures and one evidence failure; rejected. See the [Luna control summary](results/omission-controls-openai-v1/summary.json).
- `openai/gpt-5.5` high: **12/12 passed**, detecting all six omissions in both presentation orders, passing their preserved counterparts, and preferring the preserved documents. All **360 untouched-atom assessments passed**; selected. See the [GPT-5.5 control summary](results/omission-controls-openai55-v1/summary.json).

An attempted Astra judge command was rejected locally by the different-model guard, with **zero provider calls**. Astra judging was not tested. No field-test quality wins were used to select the replacement model.

## Separate replacement study

`full-openai55-v1` reuses the exact **325 writer attempts**, byte-for-byte, with source-manifest provenance, artifact hashes, and **zero new writer calls**. Its complete **270-job judging plan** uses fresh GPT-5.5 judgments across development and holdout; it does not combine successful Copilot judgments with GPT-5.5 judgments. See the [replacement manifest](results/full-openai55-v1/manifest.json).

The fixtures, prompts, splits, pairing/orders, response fields, validation tests, bounded retry policy, bootstrap, and adoption criteria remain those in [FULL-EVALUATION.md](FULL-EVALUATION.md). The primary analysis equally weights held-out documents, excludes swaps, and uses a category-stratified 95% percentile bootstrap with 10,000 resamples and seed 46075. Adoption requires a positive lower bound, no paired requirement-failure increase, no confirmed new critical regression, and the original coverage thresholds.

Writer and replacement judge are different models from the same provider; correlated errors remain a limitation. Calibration success does not establish independence.

## Interruption and resumption

A **40-minute shell-command timeout** occurred after **213 judge jobs finished: 212 valid and one failed**. Six judge runtime calls were in flight, interrupted, and recorded as incomplete. This is an interruption snapshot, not final coverage.

Six orphaned local servers—PIDs **94488, 94490, 94491, 94492, 94493, 94495**—were verified to have **PPID 1** and matching adapter commands, then explicitly terminated. Resuming the interrupted jobs uses their bounded second attempt, retaining the incomplete first-attempt artifacts.

Retain every attempt artifact and unknown usage value. Copied writer usage is historical, not new generation. Missing usage is unknown, not zero; adapter-reported costs do not establish complete provider billing or provider-internal retry usage.

From the repository root, resume in batches of at most 24 jobs to avoid another wall-clock limit:

```sh
python3 -B evals/documenting/full.py judges --output evals/documenting/results/full-openai55-v1 --split holdout --concurrency 6 --limit 24
```

Repeat for remaining eligible jobs; each invocation preserves the two-attempt cap.

## Analysis bookkeeping

Working-copy frozen runtime files stayed unchanged, including generic `full.py`. In `full_analysis.py`, the `1e-12` roundoff fix is solely a numerical tolerance at the paired nonincrease boundary, not a material noninferiority margin. Recorded transport classification now takes priority over error wording in the analysis helper; this changes reporting, not generation.

Original partial report: [analysis.md](results/full-v1/analysis.md), with detailed machine-readable data in the local `results/full-v1/analysis.json` artifact. Its partial findings are not replacement-run results.
