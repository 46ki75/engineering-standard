# Lefthook workflow evaluations

## Disposable guide evaluation

The [September 17, 2026 report](results/2026-09-17/report.md) evaluates the current configuration guide with Lefthook 2.1.14 in a fresh synthetic repository and a disposable clone of `engineering-standard`. It covers both glob matchers, native-tool parity, selection, failure propagation, real Git commits with partial staging, output controls, and deliberately broken configurations.

[`evaluate-guide.py`](evaluate-guide.py) builds the [guide-derived fixture](guide-case.yml), provisions locked dependencies, and retains command logs and before/after evidence outside the source repository. Its regression uses the source repository's committed HEAD; its fixture uses the working-tree guide, tool manifests, and evaluation files, whose exact contents and hashes are frozen in the export.

Prerequisites: the versions in `mise.toml`, Python 3.12, and Cargo/rustc 1.98.0 with rustfmt and Clippy. The runner verifies tool versions. Dependency provisioning can use the network; Python uses a run-local download cache and pnpm reuses its package store. Each repository has its own installed dependencies. Use an existing, approved temporary directory with a short path: macOS limits the Unix socket path used by tsx.

```sh
uv run --locked --no-sync python evals/lefthook/evaluate-guide.py \
  --scratch "$TMPDIR" \
  --output evals/lefthook/results/new-run
```

`--output` must be new. The original source files, HEAD, Git status, and index are compared before exporting the intentional result files. Repositories and raw logs remain in the printed temporary run directory for diagnosis. An optional `--calibration-run <directory>` retains an earlier run alongside the main results.

Verify the retained evidence offline:

```sh
uv run --locked --no-sync python evals/lefthook/verify-guide-results.py \
  evals/lefthook/results/2026-09-17
```

This is an execution-based adoption check on macOS arm64. It does not measure independent-user usability or editor-buffer behavior, and it does not re-evaluate every tool in the `internal` example.

## Historical native-tool evaluation

Verified on September 16, 2026 against `46ki75/internal` at `8af4521c5ff8ab4d254e0d956c0097274a0f37ae`, with the updated [example configuration](../../skills/engineering-standard/references/lefthook/lefthook.example.yml) and agent hooks applied locally.

### Result

The `lint`, `fmt`, `fmt-check`, and project-wide `check` contracts work with the repository's native tools. The behavioral evaluation passed 42 hook invocations plus actual agent-hook checks. The full `check` gate correctly failed on existing source-quality issues.

The original run used `output: false`. The current example defaults to job summaries and skip explanations; its commands and file selection are unchanged. Silence probes now explicitly set `LEFTHOOK_OUTPUT=false`.

| Full-project job                                               | Result                                                                                          |
| -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Cargo formatting check                                         | Passed                                                                                          |
| Clippy, all workspace crates/targets/features, warnings denied | Passed                                                                                          |
| Prettier formatting check                                      | Passed                                                                                          |
| ESLint                                                         | Passed                                                                                          |
| Terraform formatting check                                     | Passed                                                                                          |
| Ruff lint                                                      | Passed                                                                                          |
| TypeScript type checking                                       | Passed                                                                                          |
| Python type checking                                           | Passed after workspace dependencies were synchronized                                           |
| Ruff formatting check                                          | Failed: `python/ag-ui-server/src/ag_ui_server/session_store.py` needs formatting                |
| Markdown checks                                                | Failed: six existing errors across `crates/feed/README.md` and `crates/logs-reporter/README.md` |
| Stylelint                                                      | Failed: 126 existing errors; confirmed with the direct project command                          |
| Aggregate `check`                                              | Failed, propagating the leaf-hook failures                                                      |

The Ruff formatting difference was reproduced before changing the hooks. The Markdown/CSS files reporting errors were unchanged by this work. Tests remain in the repository's existing test commands and were not added to `check`.

### Behavioral coverage

[`verify.py`](verify.py) exercises the actual tools using temporary untracked probes in `internal` and an independent local clone for workspace-wide formatting and staging:

- Dirty Python, TypeScript, CSS, Terraform, and root/nested Markdown inputs fail `fmt-check`, change under `fmt`, then pass verification and remain stable on a second format.
- Explicit file selection handles spaces, Unicode, apostrophes, and ampersands. Bare tracked-file selection excludes untracked probes.
- Ignored spec files, generated OpenAPI code, and excluded agent documents are skipped. Nonmatching files skip all unrelated jobs, including project-scoped Clippy.
- A Ruff lint error remains a failure without changing the file.
- The after-write agent hook normalizes an absolute path; the stop hook captures a formatting failure and returns a blocking JSON diagnostic.
- Cargo formatting uses workspace metadata. A bare Python format invocation fixes the existing formatting difference in the disposable clone.
- Pre-commit stages formatted content while preserving the tested file's unstaged changes outside the index.
- Successful scoped runs are silent with the quiet override; failed runs carry diagnostics and nonzero exit codes.

The script checks the original repository's tracked-file hashes, Git status, and staged diff before and after the probes. It removes its probes even after an assertion failure. Its agent-hook test assumes the repository's existing changed-file selection passes the scoped checks except for the deliberate probe; unrelated dirty files may need a separate evaluation checkout.

### Environment and reproduction

Tools: Lefthook 2.1.10, pnpm 9.12.3, Rust 1.93.0, Prettier 3.6.2, Ruff 0.15.19, Terraform 1.16.2, and Pyright 1.1.410 on macOS arm64. The YAML uses the installed Lefthook's default glob matcher.

The existing Node dependencies were reused. `uv sync --locked --all-packages --all-groups` supplied missing Python workspace dependencies without changing the lockfile. Terraform was initially absent from PATH; a Terraform 1.16.2 installation under the evaluation's temporary tool directory was prepended to PATH for verification. Provision Terraform through the target project's tool manager for routine use.

From this repository, with the native tools on PATH and the example installed in `internal`:

```sh
python3 evals/lefthook/verify.py \
  --repo "$HOME/org/46ki75/internal" \
  --scratch "$TMPDIR"
```

The Python script compares the resolved target configuration with the published example, allowing a different top-level `output` setting. Review existing target configuration and agent hooks before applying that project-specific example elsewhere.

From `internal`, run the full validation gate separately:

```sh
pnpm exec lefthook validate
pnpm exec lefthook run check
```

The current example enables `summary`, `success`, `failure`, and `skips`. Use `LEFTHOOK_OUTPUT=false` for failure-only output, or add `execution_out` to the enabled output types for successful commands' detailed output.

This evaluation verifies CLI and disk-based agent hooks. Editor-buffer formatting and cross-platform behavior require their own checks.
