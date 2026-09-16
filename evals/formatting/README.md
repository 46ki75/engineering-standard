# dprint formatting evaluation

**Evaluation complete, with qualified adoption:** the [report](results/2026-09-16/report.md) supports a concise rule for repositories using dprint and a minimal stdin-only configuration. Exec 0.7.3 failed process-lifecycle gates; the combined editor save pipelines also require explicit integration decisions.

## Objective and protocol

Evaluate dprint as a formatter multiplexer while retaining project-selected formatters. Prefer the least complex configuration that satisfies correctness, scope, and integration requirements. Existing lint/type/test commands supply compatibility evidence.

The source is `46ki75/internal` at commit `8af4521c5ff8ab4d254e0d956c0097274a0f37ae`. The runner creates independent committed-snapshot clones, isolated tool state and caches, and dedicated editor profiles. It checks the original repository's HEAD and status without reading its modified `opencode.jsonc`. All formatting and hook mutations occur in evaluation clones.

The comparison covers Rust/rustfmt, web TS/TSX/CSS and Markdown/Prettier, Python/Ruff, Terraform, and a Markdown/markdownlint alternative. Project inputs and configuration are frozen before the main corpus comparison. Synthetic cases cover paths, line endings, nested configuration, exclusions, and failures.

Gates:

- Byte-identical direct/delegated output under equivalent settings; repeated-format stability.
- Hash-proven source preservation by checks and intended file selection.
- Visible errors, preservation of failing input, and process cleanup.
- Agreement between cached and uncached checks after configuration/version changes.
- Actual editor saves, scoped hooks, and baseline-relative compatibility checks.
- Warm changed-content save p95 at most 500 ms for representative files.

The minimal candidate disables incremental formatting. The cache-enabled comparison adds external dependency tracking. A nested Rust configuration tests the small declarative extension needed when file context changes. The evaluation records failed gates as failures rather than weakening the adoption criterion.

## Reproduce

The current setup driver targets **macOS arm64** and requires Python 3.9+, Git, Node, dprint, rustup, uv, Neovim, and VS Code. It downloads pinned tools and installs locked Node dependencies with lifecycle scripts disabled. Editor reproduction uses the installed plugin/extension snapshots listed in the manifest; full personal VS Code state is not required.

Choose a fresh, approved temporary path outside the source repository. Run phases in order; replace `$RUN` and `$SOURCE` with explicit paths:

```sh
python3 evals/formatting/run.py setup --root "$RUN" --source "$SOURCE"
python3 evals/formatting/run.py pilot --root "$RUN"
python3 evals/formatting/run.py corpus --root "$RUN"
python3 evals/formatting/run.py behavior --root "$RUN"
python3 evals/formatting/run.py timing --root "$RUN"
python3 evals/formatting/run.py compatibility --root "$RUN"
python3 evals/formatting/run.py hooks --root "$RUN"
python3 evals/formatting/run.py editors --root "$RUN"
python3 evals/formatting/run.py representative --root "$RUN"
python3 evals/formatting/run.py editor-actions --root "$RUN"
python3 evals/formatting/run.py extensions --root "$RUN"
python3 evals/formatting/run.py example --root "$RUN"
python3 evals/formatting/run.py export --root "$RUN" --output evals/formatting/results/new-run
```

Keep timing phases free of concurrent builds or other evaluation work. Each timed scenario has five warm-up pairs and 100 measured changed-content requests; direct/candidate order alternates. Editor measurements time real save operations. Cold-start samples use fresh dprint caches and include plugin download/extraction; they are not cold-OS-cache measurements.

Neovim uses copied LazyVim state and its registered `BufWritePre` callback, with `UIEnter` explicitly fired during headless startup. VS Code runs an extension-host test against real `TextDocument.save()` operations in isolated application profiles. Its macOS socket-path limit requires short profile paths next to the evaluation directory. The multi-root test copies `.code-workspace` to `evaluation.code-workspace` so the CLI recognizes it as a workspace.

`rust-compatibility` and `vscode` are targeted recovery phases for the recorded calibration issues. They are unnecessary for a fresh run with the corrected harness. Repeated integration phases create new clones/profiles; earlier artifacts are retained. Corpus runs are intended for a fresh baseline, not for reuse after formatting.

## Artifacts and interpretation

The [result directory](results/2026-09-16/) contains:

| Artifact | Contents |
| --- | --- |
| `report.md` | Decision, tradeoffs, failed gates, and coverage limits |
| `manifest.json` | Source commit, tool versions, configurations, checksums, host, and harness hashes |
| `summary.json` | Consolidated outcomes |
| `evidence.json` | Exit statuses, hashes, diagnostics from controlled probes, and editor observations |
| `corpus.json` | Per-file input/output hashes and equivalence/stability results |
| `timings.csv` | Individual measured samples |
| `usability.json` | Paired text-only agent usability observations and task provenance |

Complete command stdout/stderr and editor profiles remain under the temporary run. Portable exports replace local paths and hash editor output instead of embedding project source. The original run used `dprint-eval-2026-09-16-v2` beneath the approved OpenCode temporary directory.

The [frozen candidate](rule.md) preceded independently generated [usability scenarios](usability-cases.json). Fresh baseline/candidate sessions planned commands for the same eight scenarios. This checks instruction clarity; it is not autonomous execution or a statistical efficacy claim.

Verify the retained evidence offline:

```sh
python3 evals/formatting/verify.py
```
