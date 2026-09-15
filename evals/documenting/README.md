# Fixed-draft documentation evaluation

## Status and purpose

**Full evaluation complete:** see the [final report](results/full-openai55-v1/report.md), [full-suite protocol](FULL-EVALUATION.md), and [provider-recovery record](RECOVERY.md). The decision is to retain the short rule rather than require the longer candidate. The remaining sections document the initial calibration protocol.

Calibration results: [September 15, 2026 report](results/calibration-2026-09-15-v2/report.md). The host-based run completed nine revisions and twelve judgments; two judgments failed the response schema. The report includes the usage estimate and required judging improvements before scaling.

The user approved **host-based fixed-draft calibration before full-scale evaluation**. Offline runner tests and preflight have passed, and the first calibration writer has started. The [candidate reference](../../skills/engineering-standard/references/documenting/README.md) and prompts are frozen; improvement over existing guidance has not been established.

[`run.py`](run.py) implements the three-case calibration only. The 36-case evaluation remains planned, requires a full-suite driver, and needs budget approval after calibration.

This is a controlled text-only comparison of guidance for finalizing fixed drafts. Guidance is injected directly in fresh custom-agent sessions. It does not assess initial drafting, research, actual skill loading, or the normal agent's whole workflow.

## Conditions and prompt assembly

[writer.md](prompts/writer.md) is the **common system prompt for all conditions**. The runner appends a newline and the arm's guidelines, preserving the common prompt without an extra review instruction:

| Arm | Guidance |
| --- | --- |
| A | `skills/engineering-standard/SKILL.md` with its unique documentation-rule bullet filtered out; every other guidance line remains in order. |
| B | The complete current `SKILL.md`, including the short documentation rule. |
| C | B plus `\n## Documentation review\n`, followed by the body of `## Review and revise` and the complete `## Short examples` section. |

The documentation rule is:

> After creating or updating documentation, review the affected document as a whole before finalizing it. Identify and fix unnecessary repetition, duplicate explanations, and inconsistencies. Address organization before sentence-level wording, and preserve necessary context and technical meaning.

C excludes the reference's title, candidate-status paragraph, original `## Review and revise` heading, and `## Sources` section. The manifest freezes the assembled prompts and source hashes; subsequent commands reject changed inputs or runner code for that output directory.

Each case's task, source facts, and original draft form the same user message across arms. Writers receive no evaluation annotations, other candidates, or judge feedback. The runner sends the exact user-prompt text through **stdin**, avoiding v1.18.31's positional-message re-quoting. Diagnostic commands use closed stdin (`DEVNULL`). Sessions are created afresh without continuation or forks; shared session storage does not reuse model history.

- Writer: fixed `openai/gpt-6-astra`, `high` reasoning variant.
- Judge: `github-copilot/claude-sonnet-5`, provider-default variant.
- Both roles use the custom primary agent `documentation-eval`, denied tool permissions, and the same requested output limit of **16,000 tokens**. Provider-side enforcement of that limit is not verified.

The custom-agent prompt replaces the provider-specific default prompt, but OpenCode environment context and provider/authentication transforms remain. Stored prompts are the exact assigned inputs, not a capture of the entire effective provider request or system prompt.

## Isolation and preflight

Each invocation uses a temporary working directory outside the repository and a sanitized child environment:

- `HOME`, `XDG_CONFIG_HOME`, `XDG_STATE_HOME`, and `OPENCODE_CONFIG_DIR` are isolated. `OPENCODE_TEST_HOME` is sanitized out and is **not set**.
- Original `XDG_DATA_HOME` is shared for existing authentication and session persistence; original `XDG_CACHE_HOME` is shared for package/model caches. Their default paths are resolved from the original home before isolation. The runner does not copy or inspect credentials or modify the original global configuration.
- `OPENCODE_CONFIG_CONTENT` supplies the custom configuration. Project configuration, Claude compatibility instructions, and external skills are disabled. External plugins are disabled with pure mode; built-in authentication plugins remain available.
- Runtime preflight verifies matching assigned agent prompts/models, **all resolved tools disabled** for both roles, and no configured instructions, plugins, or MCP servers. No user/project skills are loaded; the built-in `customize-opencode` skill may still be listed, but the disabled skill tool cannot invoke it.

Preflight also pins OpenCode to **1.18.31** and checks model metadata for both models and the writer's `high` variant. It stores exposed model IDs, limits, capabilities, options, variants, and costs. These diagnostics verify configuration and metadata availability without a generation call; they do not verify provider enforcement of every requested setting.

Relevant controls were checked against source tag `v1.18.31`:

| Source | Controls used |
| --- | --- |
| [CLI](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/opencode/src/cli/cmd/run.ts) | `run --agent --model --variant --format json`, stdin prompt transport, fresh sessions. |
| [Configuration](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/opencode/src/config/config.ts) and [instructions](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/opencode/src/session/instruction.ts) | `OPENCODE_CONFIG_CONTENT`, `OPENCODE_CONFIG_DIR`, `OPENCODE_DISABLE_PROJECT_CONFIG=1`. |
| [Runtime flags](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/opencode/src/effect/runtime-flags.ts) and [plugins](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/opencode/src/plugin/index.ts) | `OPENCODE_DISABLE_CLAUDE_CODE=1`, `OPENCODE_DISABLE_EXTERNAL_SKILLS=1`, `OPENCODE_PURE=1`, and `OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX=16000`; default auth plugins remain enabled. |
| [Global paths](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/core/src/global.ts) and [auth storage](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/opencode/src/auth/index.ts) | Isolated home/config/state with shared original data and cache paths. |

## Calibration and planned evaluation

Calibration checks the harness, prompt isolation, output/schema handling, positional consistency, throughput, and cost accounting. Do not tailor the frozen candidate to calibration fixtures. Three documents support descriptive findings, not efficacy, confidence-interval, significance, or adoption claims.

| Phase | Writers | Fresh judge sessions | Total sessions |
| --- | ---: | ---: | ---: |
| Implemented calibration | 3 fixtures × 3 arms × 1 repetition = **9** | 3 fixtures × 2 comparisons × 2 orders = **12** | **21** |
| Planned full evaluation | 36 cases × 3 arms × 3 repetitions = **324** | 216 primary comparisons + 54 order swaps = **270** | **594** |

Calibration compares A/B and B/C on every case in both left/right orders. Writer jobs are shuffled with seed `46075`; judge jobs use `46076`. Each judgment gets a fresh session and reuses the same completed writer outputs.

The full-suite plan is **12 development and 24 held-out cases**, split by document family, including flawed and legitimately clean documents. Candidate development is restricted to development families; freeze prompts, cases, rubric, and analysis decisions before held-out evaluation. Candidate authors must not inspect held-out fixtures.

For that planned suite, A/B and B/C comparisons within each case/repetition yield `36 × 3 × 2 = 216` primary judgments; a prespecified 25% order-swap sample adds `54`. The **594-session** total excludes calibration, development repeats, and reruns. Repetitions and order swaps are dependent observations, not additional independent documents.

## Blinding, analysis, and adoption

All judges use [judge.md](prompts/judge.md), with the task, source facts, original draft, requirement/issue annotations, and anonymous left/right documents. Arm/model metadata is withheld; arm mappings are saved separately. The runner validates the exact JSON shape, enums, score ranges, evidence fields, and complete, unique requirement/issue ID coverage on both sides.

The rubric distinguishes inherited errors from new regressions, permits uncertainty and ties, and accepts unchanged clean drafts with empty issue arrays. Fidelity and task usability take priority over length; necessary detail and repetition are not defects. Critical regressions block adoption; tied evidence favors shorter guidance.

The current summary reports recorded sessions and usage, writer word counts/preservation-check failures, paired votes, and order agreement. Detailed requirements, issues, regressions, and scores remain in individual judgments. Preservation checks are semantic proxies, not proof of correctness. Track A/B baseline failures and missing trials alongside comparisons; an absent judgment is not a tie. Any later adoption decision needs held-out evidence and measured cost, with development results reported separately.

## Runner commands

Run from the repository root with a unique `runID`. Results persist under `evals/documenting/results/runID`, outside temporary execution directories. These commands run calibration; there is no full-suite execution mode.

```sh
python3 evals/documenting/run.py validate
python3 -m unittest discover -s evals/documenting/tests -v
python3 evals/documenting/run.py preflight --output evals/documenting/results/runID
python3 evals/documenting/run.py writers --output evals/documenting/results/runID --limit 1 --concurrency 1
```

After the initial writer completes and its harness behavior is checked, continue with the same output directory. Completed trials are skipped; omitting `--limit` schedules all remaining jobs:

```sh
python3 evals/documenting/run.py writers --output evals/documenting/results/runID --concurrency 3
python3 evals/documenting/run.py judge --output evals/documenting/results/runID --concurrency 3
python3 evals/documenting/run.py summarize --output evals/documenting/results/runID
```

The test command is offline. Generation requires a saved successful preflight. Concurrency defaults to `3`; writer/judge invocations have a default `600`-second timeout, adjustable with `--timeout`.

The runner performs no retries. Failed or incomplete trials block resume and require a new output directory; preserve the original attempt when intentionally rerunning a known initial CLI failure. CLI errors/timeouts, tool events, malformed events, empty responses, unexpected completed-step counts/finish reasons, and invalid judge JSON are recorded as failures. OpenCode may retry internally, but those provider attempts are not exposed.

## Artifacts and budget decision

The implementation stores:

- `manifest.json`: creation time, calibration stage, seed/job order, host metadata, requested models/variant/output limit, required CLI version, whole case objects, assembled prompts, and `source_hashes` for the skill, reference, prompts, and runner. It contains neither a Git revision nor separate per-case digests.
- `preflight.json` and `preflight-*.txt`: CLI version, path/config/agent/skill diagnostics, resolved tool checks, and available model metadata.
- Each trial: `system.md`, `input.md`, `config.json`, `output.md`, `events.jsonl`, `stderr.txt`, `stdout-noise.txt`, and `result.json`. Results include status/failures, requested model/variant, elapsed seconds, exit/timeout state, session IDs, input/system/output hashes, output word count, observed completed model steps, finish reasons, and reported token/cost totals. Reasoning events are excluded from the saved event stream.
- Writers: `checks.json`. Judges: `mapping.json` and, for valid responses, `judgment.json`.
- `summary.json`: descriptive calibration results and projections for 324 writers/270 judges, including serial runtime, tokens, and reported cost.

Summary session counts cover trials with `result.json`; compare them with the expected 9 writers/12 judges to identify missing or incomplete work. Observed completed steps are **not true provider-attempt counts**. Missing usage is unknown even when a numeric aggregate is zero. Likewise, OAuth-reported cost of `0` does not mean free usage, and reported-cost projections are not billing estimates.

After calibration, use observed usage, latency, failures, and order disagreements to assess harness readiness and the proposed 594-session budget. Account for unknown usage/pricing and repeat-run overhead before requesting full-scale budget approval.
