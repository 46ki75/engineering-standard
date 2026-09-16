# Lefthook guide evaluation

## Decision

**Valid and effective for the tested workflow, with one documentation clarification.** The guide-derived configuration passed the behavioral checks on Lefthook 2.1.14, and the current repository's eight configured gates passed in an independent clone. A matching nonexistent path can reach a native tool and fail; it is not necessarily skipped.

The final run passed **31 scenarios and 115 explicit Lefthook hook invocations**. The scenario count includes setup, the repository regression, and original-source preservation. Two installed-hook scenarios additionally exercised real Git commits. Four deliberately defective configurations produced the failures or false successes that the evaluation's selection, parity, propagation, and preservation checks are designed to detect.

## Inputs and method

- Repository baseline: `1d6394f9f0af067ea558fa7116bf82ca386894df`.
- Platform: macOS 27.0, arm64.
- Tools: Lefthook 2.1.14, Node 24.20.0, pnpm 12.4.1, uv 0.12.9, Python 3.12.14, Prettier 3.6.2, Ruff 0.15.19, TypeScript 7.0.2, and Cargo/rustc 1.98.0.
- Candidate: [`guide-case.yml`](../../guide-case.yml), derived from the configuration guide before the first run. Its bytes are identical between calibration and final evaluation. Matcher-specific variants and deliberate defects are applied only in disposable repositories.
- Fixture: root/nested Python and Markdown, a nested TypeScript package with a different Prettier policy, a two-crate Rust workspace, and a Node test. Dependencies are provisioned before hooks run.
- Each scenario starts from a committed fixture baseline. Direct native-tool commands provide comparison results. Source-file hashes, Git status, HEAD, and index contents verify preservation; dependency, build, and interpreter cache directories are outside the source-content comparison.

The original worktree is checked before and after execution, before intentionally exporting results. All fixture formatting, staging, commits, and regression execution occur in temporary repositories. The regression tests committed HEAD; the synthetic fixture tests the working-tree guide and evaluation files frozen in `inputs/`.

## Results

| Area                      | Observed result                                                                                                                                                                                                                                          |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Configuration             | `validate` and JSON `dump` succeeded; the clean aggregate passed.                                                                                                                                                                                        |
| Matcher behavior          | Both default `gobwas` with paired patterns and `doublestar` routed root/nested inputs correctly. A separate probe confirmed the different root-level behavior of `**/*.py`. Exclusions were exercised with both matchers.                                |
| Selection                 | Bare and `--all-files` runs selected tracked inputs. Repeated `--file` selected untracked paths containing spaces, Unicode, apostrophes, and ampersands. Nonselected tracked input stayed unchanged.                                                     |
| Skips and missing paths   | Excluded and nonmatching paths visibly skipped. A missing matching Python path failed in Ruff under `fmt`, `fmt-check`, and `lint`; a missing nonmatching path skipped.                                                                                  |
| Formatting                | All 12 root/nested, two-matcher cycles changed dirty input, passed subsequent checks, were idempotent, and matched direct native output byte-for-byte.                                                                                                   |
| Context and project scope | Nested-package policy applied, including invocation below the Git root. A Cargo manifest triggered project-wide Clippy without `{files}`; a nonmatching Markdown path skipped it. Selecting one Rust file intentionally formatted both workspace crates. |
| Read-only checks          | Successful and deliberately failing checks preserved source content and the index.                                                                                                                                                                       |
| Aggregate failures        | Independently injected lint, formatting, type, and test defects failed the aggregate with native diagnostics, even with an unrelated outer `--file` selection.                                                                                           |
| Installed pre-commit      | A real successful commit contained formatted staged content. A parser error blocked another commit. Both preserved the tested unstaged content outside the index and left an unstaged-only file untouched.                                               |
| Output                    | Default summaries, quiet success, detailed success output, successful stderr suppression, and failure diagnostics behaved as documented.                                                                                                                 |
| Negative controls         | Bad glob, write/check scope mismatch, swallowed aggregate failure, and mutating check were all detected.                                                                                                                                                 |
| Original worktree         | Source content, HEAD, Git status, and index matched their pre-execution state.                                                                                                                                                                           |

The independent `engineering-standard` clone passed all eight jobs: lint, formatting, TypeScript checking, Node tests, Python tests, calibration tests, formatting-evidence verification, and Python lockfile verification. Its source and index remained unchanged.

Single-run timing observations: the successful fixture commit took 0.4472 seconds including Git and the installed hook; the repository aggregate took 15.159 seconds. These are recorded observations, not a latency benchmark or percentile estimate.

## Calibration findings and corrections

The [initial run](calibration/results.json) passed 28 of 30 scenarios. Its failures and original inputs are retained rather than replaced with final outcomes.

1. **Missing-path assumption:** the initial harness expected `--file missing.py` to skip. Lefthook passed the matching path to Ruff, which reported `No such file or directory`. The guide previously grouped missing paths with paths that can skip. The clarification now distinguishes excluded/nonmatching paths from matching nonexistent paths. The final case verifies failures for the latter and skips for a missing nonmatching path; a direct Ruff invocation also fails.
2. **Temporary-path limit:** the cloned repository's Node gate failed because tsx could not open its Unix socket under the long run-specific `TMPDIR`. The same native Node test command reproduced the error. Using the shorter approved scratch parent passed all 12 Node tests, and the final full aggregate passed. The runner now uses that parent as `TMPDIR`; the fixture and clone directories remain run-specific. This was an evaluation-environment failure, not a hook-routing failure.

The final run adds an explicit matcher-depth/exclusion scenario and verifies source preservation even when a read-only command unexpectedly fails. It uses the same guide-derived configuration as calibration.

## Effectiveness and coverage

The guide supplied enough information to construct and execute the synthetic configuration successfully, including project context, explicit selection, aggregate scope, and staging behavior. No corrective changes to that configuration were needed after execution began. The missing-path clarification makes the selection guidance more precise.

This is one execution-based adoption exercise performed by the implementing agent. It supports the documented contracts in the tested macOS environment; it is not an independent-user usability study or a cross-platform claim. Editor-buffer behavior, every possible partial-staging conflict, and the `internal` example's Terraform, ESLint, Stylelint, Pyright, and markdownlint policies are outside this run. Earlier integration evidence remains in the [evaluation index](../../README.md#historical-native-tool-evaluation).

## Evidence and reproduction

| Artifact                         | Contents                                                                              |
| -------------------------------- | ------------------------------------------------------------------------------------- |
| [`manifest.json`](manifest.json) | Versions, baseline revision, frozen-input hashes, fixture hashes, and evidence hashes |
| [`results.json`](results.json)   | Scenario outcomes and preservation/parity assertions                                  |
| [`commands.json`](commands.json) | Arguments, working directories, exit statuses, durations, stdout, and stderr          |
| `inputs/`                        | Exact evaluated guide, configuration, runner, and tool manifests                      |
| `calibration/`                   | Initial failed outcomes and their frozen inputs                                       |

See the [runner instructions](../../README.md#disposable-guide-evaluation) for a fresh execution. The retained result's UTC start time is in the manifest; this directory uses the local evaluation date, September 17, 2026. Main-run paths are normalized to `$RUN`, `$SOURCE`, `$SCRATCH`, and `$HOME`; the calibration export retains its original path normalization.

Verify the portable evidence without provisioning Rust or running the hooks again:

```sh
uv run --locked --no-sync python evals/lefthook/verify-guide-results.py \
  evals/lefthook/results/2026-09-17
```
