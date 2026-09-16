# dprint formatting evaluation — September 16, 2026

## Decision

**Adopt the concise operational rule for repositories configured with dprint, and retain a minimal, declarative stdin-only configuration pattern.** The best measured balance was one project configuration, five command mappings, no formatter adapters, and incremental formatting disabled.

**Unconditional rollout of exec 0.7.3 does not pass the gates.** A signal-terminated formatter hung, and timed-out/canceled children continued running. The existing combined VS Code save pipeline also canceled some first saves. These results limit the recommendation despite successful ordinary formatting and dprint-only editor integration.

The [historical reference](../../../../skills/engineering-standard/references/formatting/dprint.md) contains the evaluated operational guidance and [tested configuration](../../../../skills/engineering-standard/references/formatting/dprint.example.json).

## Environment and coverage

- Source: `46ki75/internal`, commit `8af4521c5ff8ab4d254e0d956c0097274a0f37ae`.
- Host: macOS 26.6.2, Apple M5 Pro, 48 GiB memory.
- dprint 0.57.4; exec 0.7.3; Prettier 3.6.2; Rust 1.93.0/rustfmt 1.8.0; Ruff 0.15.19; Terraform 1.16.2; Node 24.20.0; pnpm 9.12.3.
- Neovim 0.12.5 with copied LazyVim/Conform state; VS Code 1.137.0 with dprint extension 0.17.2 and the relevant formatting/fix extensions.
- Main corpus: **263 project files + 20 synthetic cases = 283 files**: 111 Rust, 14 Markdown, 15 Python, 18 Terraform, 68 TSX, 35 CSS, and 22 TypeScript files.

Independent clones and dedicated tool/editor state isolated all mutations. The source repository's HEAD and status remained unchanged, including its existing modified `opencode.jsonc`, which was not read. No personal editor settings were changed. Exact versions, configuration hashes, and plugin commits are in the [manifest](manifest.json).

## Gate results

| Gate | Result |
| --- | --- |
| Direct/delegated output | **Pass:** 283/283 byte-identical; no formatter errors |
| Repeated formatting | **Pass:** stdin and bulk output stable; bulk matched stdin |
| Non-mutating check | **Pass for selected stdin commands:** input hashes preserved; exit 20 before formatting and 0 afterward |
| File selection | **Pass:** generated/ignored files preserved; spaces, Unicode, quotes, brackets, and braces exercised |
| Normal failures | **Pass:** syntax errors, missing executables, and invalid configuration surfaced without changing failing input |
| Process lifecycle | **Fail:** signal-exit hang; children outlived timeout and CLI interruption |
| Cache correctness | **Fail without dependencies; pass for the tested tracked dependency and disabled-cache variants** |
| dprint-only saves | **Pass:** Neovim and VS Code, including VS Code multi-root operation |
| Combined save pipeline | **Fail for exact parity/reliability:** extra TOC content in Neovim; canceled first saves in VS Code |
| Warm-save p95 ≤500 ms | **Pass:** largest representative scenario p95 was 121.8 ms |
| Final published example | **Pass:** selected all 263 project files, preserved checks, matched evaluated output, and was idempotent |

The main corpus changed 22 files, including 18 synthetic cases. Four project files changed: three Markdown documents and one Python file. Native `cargo fmt --all` output also matched the Rust stdin mapping after the evaluation environment's Cargo proxies were corrected.

## Configuration tradeoffs

| Variant | Benefit | Cost or limitation | Decision |
| --- | --- | --- | --- |
| Stdin exec, `incremental: false` | External settings are read on each invocation; simple maintenance | Executes the delegate for unchanged checks | Preferred starting pattern |
| Incremental exec with dependency keys | Much faster unchanged and bulk checks | Configuration and formatter-version dependency tracking must remain complete | Opt-in after invalidation tests |
| Scoped Rust configuration | Restores nested rustfmt context and a different edition declaratively | One additional configuration at the differing subtree | Use when required |
| File-writing delegate | Can invoke write-only tooling | The probe mutated its source during `dprint check` | Rejected for the standard pattern |

Concrete findings:

- Double-brace `{{file_path}}` HTML-escaped `&`; `{{{file_path}}}` preserved literal paths. Exec tokenizes arguments before substitution.
- Applying the web `.prettierignore` to files outside that workspace produced successful no-ops. Separate web and Markdown mappings fixed this. Deliberately unformatted probes prevented a false equivalence result.
- Root-cwd rustfmt stdin invocation ignored a nested rustfmt configuration. A scoped dprint configuration restored native file-mode output.
- Changing an untracked external Prettier configuration caused cached `check` to return 0 while uncached `check` returned 20. Adding that file to `cacheKeyFiles`, or disabling incremental formatting, restored agreement.
- Changing a formatter implementation also required invalidation; updating `cacheKey` restored detection. This does not establish complete cache dependency coverage for every language.
- All 14 Markdown cases matched native `markdownlint-cli2 --fix` when delegated through its stdin `--format` mode. That output differed from Prettier on five cases. Selecting Prettier for Markdown is a style/workflow decision, not a dprint equivalence result.
- The uv-backed Ruff mapping matched direct Ruff output. The final example uses the locked, pre-synchronized uv environment.

## Performance

Each row uses 100 changed-content measurements after five warm-ups. Direct/candidate CLI order alternated. Representative inputs were the median-sized and largest project files for each listed extension, with a changed comment and extra trailing whitespace. Times are milliseconds; p95 uses the nearest-rank definition.

| Input | Bytes | Direct CLI p95 | dprint CLI p95 | Neovim save p95 | VS Code save p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Median Rust | 1,057 | 20.8 | 28.7 | 40.0 | 35.7 |
| Largest Rust | 21,773 | 23.5 | 31.1 | 47.0 | 40.3 |
| Median TSX | 1,651 | 67.8 | 77.1 | 86.8 | 86.9 |
| Largest TSX | 13,691 | 97.7 | 105.7 | 121.8 | 113.8 |
| Median Markdown | 2,359 | 67.5 | 74.6 | 89.8 | 79.1 |
| Largest Markdown | 9,840 | 76.9 | 83.1 | 99.6 | 89.3 |

Small Rust/Markdown/TSX/Python/Terraform scenarios also passed the threshold. An unchanged TSX check had p95 68.3 ms without incremental formatting and 11.6 ms with it. Five non-incremental bulk runs took 1.21–1.24 seconds; warmed incremental bulk runs took about 56 ms after the initial population run. These bulk measurements are not comparisons with native batched Prettier.

Three fresh dprint-cache starts took 0.86–1.13 seconds, including plugin download/extraction. The warm-save target does not describe first-time installation. Raw measurements are in [timings.csv](timings.csv); this single-host study does not establish cross-platform latency.

## Integration and compatibility

Neovim exercised LazyVim's registered save callback through actual writes of unsaved buffers. Headless startup explicitly fired `UIEnter`; a callback assertion prevented a false no-format pass. The original formatter lists did not format the TSX/CSS probes. The dprint mappings covered the tested languages, including Neovim's `tf` filetype. Restoring `markdown-toc` added TOC content beyond CLI output.

VS Code used real extension-host `TextDocument.save()` operations. Folder and multi-root dprint-only profiles matched direct output. A long-lived extension session picked up a changed external Prettier configuration without restart when incremental formatting was disabled.

With `source.fixAll` restored, the first Markdown and CSS saves returned `false`; the disk retained its old content and the buffer retained the edits. A second save succeeded and matched the formatter output. This was reproduced in a follow-up that preserved the unsaved buffer. The corresponding Prettier-plus-save-actions baseline completed its saves. The responsible extension/order interaction was not isolated, so the combined pipeline remains unresolved.

Both original and dprint-substituted Lefthook configurations preserved the tested partially staged file: the index contained formatted staged content, while unstaged content remained outside the index. The existing per-file agent hook suppressed invalid-input failures in both configurations. An explicit dprint check detected the failure, supporting the rule's verification requirement.

| Existing check | Baseline versus dprint-formatted snapshot |
| --- | --- |
| Rust formatting, Clippy, workspace tests | Passed in both after correcting isolated Cargo subcommand/rustdoc proxies |
| Web formatting, ESLint, typecheck | Passed in both; ESLint retained seven warnings |
| Web tests | 37 tests passed, exit 0 in both; both also logged the same Nitro `ERR_LOAD_URL` diagnostic under the evaluated install |
| Stylelint | Failed in both with existing CSS diagnostics; evaluated CSS source was unchanged |
| Python Ruff lint | Passed in both |
| Python Ruff formatting | Baseline failed; formatted snapshot passed |
| Terraform formatting | Passed in both |
| Markdown lint | Baseline six errors; formatted snapshot four pre-existing MD013 errors |

These are baseline-relative compatibility results, not a claim that the repository's full validation is clean. Ignored live-service Rust tests were not invoked.

## Agent instruction probe

The short rule was frozen before eight scenarios were independently generated. One fresh baseline session and one fresh candidate session planned commands for those same scenarios.

The baseline relied on formatter exit status and proposed no explicit `dprint check` commands. The candidate proposed seven same-scope checks; for the documented-wrapper case it correctly requested the missing pinned check interface rather than inventing flags or using the global executable. Both preserved scope, exclusions, and unsaved edits and reported known failures appropriately.

This supports the wording's intended verification behavior in the probe. It is a text-only usability result, not an autonomous execution test or statistical evidence of superiority. [Usability observations and task IDs](usability.json) preserve the comparison.

## Reproduction and remaining limits

See the [runner protocol](../../README.md), [per-file hashes](corpus.json), and [detailed evidence](evidence.json). Calibration exposed harness issues with Rust proxy installation, copied Mason symlinks/Tree-sitter assets, VS Code's socket-path limit, workspace filename detection, and settings changed during startup. The corrected runs supersede those attempts; earlier logs remain in the temporary run.

The setup and editor drivers currently target macOS arm64. VS Code profiles reproduce relevant formatting/fix extensions rather than every personal extension. No range-formatting contract, Windows/Linux execution, or exhaustive editor cancellation behavior was established. Re-evaluate process cleanup and combined save actions before broadening adoption.
