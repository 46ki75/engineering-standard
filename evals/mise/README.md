# mise migration trials

Local verification on macOS arm64 with mise 2026.9.9, September 17, 2026.
The repositories are siblings of `engineering-standard` under `~/org/46ki75/`.
The reusable policy is the [mise standard](../../skills/engineering-standard/references/mise/README.md).

## Configuration

| Repository | Exact development pins                                | Native Rust                     |
| ---------- | ----------------------------------------------------- | ------------------------------- |
| `elmethis` | Node 22.23.2; pnpm 9.12.3                             | No active Rust project          |
| `web`      | Node 24.21.0; pnpm 10.6.5                             | 1.98.0 in `rust-toolchain.toml` |
| `internal` | Node 24.21.0; pnpm 9.12.3; Python 3.12.14; uv 0.12.15 | Existing 1.93.0 pin retained    |

`web` and `internal` also pin Terraform 1.16.2, AWS CLI 2.36.46, Zig 0.16.0,
and cargo-lambda 1.9.2. `internal` pins cargo-llvm-cov 0.9.1. Mise reads pnpm's
existing exact version/checksum from `package.json`; its npm dependency sidecars
are included with `mise.lock`. Locks contain Linux x64/arm64 and macOS arm64 entries.

All seven Justfiles were replaced by root namespaced tasks. The archived
`web/crates/http-api-old` recipes remain under `legacy:http-api-old:*`.
CI and devcontainers consume the repository pins. Rustup owns Rust components
and cross-compilation targets; mise owns the auxiliary CLIs.

## Results

The retained command-stub probes passed for deployment/coverage ordering, argument
and environment forwarding, failure propagation, and generated Git-hook launchers.
This repository's `mise run check` also passed after updating the standard and
disabling pnpm's implicit dependency installation.

| Verification                                                          | Result                                                                                 |
| --------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Exact tool installation and frozen dependency setup                   | Passed in all three repositories                                                       |
| `elmethis`: `core:ci`, `ag-ui-stub:ci`, `drawio:ci`, `ikuma-theme:ci` | Passed; core/stub coverage ran 34/16 tests                                             |
| `elmethis`: workspace `test`                                          | Passed: core 34, stub 16, React 498, Vue 467, Solid 322 unit + 80 SSR tests            |
| `elmethis`: workspace `check`                                         | Passed, including the Git pre-commit gate, after correcting five formatting violations |
| `web`: `web:test`, `rust:test`                                        | Frontend build, 7 unit tests, 16 SSR tests, and Rust unit tests passed                 |
| `web`: `logs-reporter:build`                                          | arm64 Linux release Lambda built successfully using mise's Zig/cargo-lambda            |
| `web`: project-wide `check`                                           | Frontend/Terraform checks passed; existing Rust formatting and Clippy findings failed  |
| `internal`: `rust:ci`, `web:ci`, `ag-ui-server:test`                  | Passed; frontend 37 tests, Python 16 tests; Rust live tests stayed ignored             |
| `internal`: `rust:coverage:ci`                                        | Passed: instrumented hermetic tests and generated `lcov.info`                          |
| `internal`: project-wide `check`                                      | Existing Ruff/Markdown formatting and 126 Stylelint findings failed                    |
| Reporter-specific tests after correcting `--lib` to `--bins`          | Passed in both Rust repositories; currently zero binary unit tests                     |
| GitHub Actions validation                                             | All workflows passed actionlint 1.7.12 with ShellCheck 0.11.0                          |
| Clean environment selection                                           | Exact Node/pnpm and native Rust/Python selection verified without shell activation     |

Full hosted Linux CI runs and devcontainer builds require their corresponding
runner/container environment. Deployment command construction and ordering were
tested with stubs; publishing and credential-dependent live tests were not run.

### Migration fixes

- A global `npm:pnpm` shadowed the discovered project pnpm pin. Adding
  `"npm:pnpm"` to project-scoped `disable_tools` restored the intended selection.
- The tested mise registry lacked short names for the Rust helper CLIs.
  `[tool_alias]` entries mapped them to `github:cargo-lambda/cargo-lambda` and
  `github:taiki-e/cargo-llvm-cov`, providing lockable prebuilt releases.
  Cargo-lambda also needs `matching = "cargo-lambda-v"`: automatic Linux asset
  selection chose Python wheels with the executable nested under `.data/scripts`.
  The explicit match selects standalone CLI archives on every locked platform.
- Both reporter crates are binary-only. Their old `cargo test --lib` recipes
  failed; the replacements use `--bins`.
- The `elmethis` pre-commit gate initially rejected formatting in
  `.design-sync/previews/ElmAudioPlayer.tsx`, `.mcp.json`, `.vscode/settings.json`,
  `opencode.json`, and `packages/react/scripts/verify-compiler-output.ts`.
  Formatting-only corrections allowed the full gate and commit to pass.

### Existing failures exposed

- `web`: rustfmt reports `crates/web-lambda-http-api/src/web_config/controller/mod.rs`;
  Clippy reports existing acronym, redundant-expression, and conversion issues.
  The previous Rust CI job executed `exit 0`; it now runs the passing unit-test task.
- `internal`: Ruff flags `python/ag-ui-server/src/ag_ui_server/session_store.py`;
  Markdown checks flag the feed and reporter READMEs. Existing CSS fails Stylelint.
  These diagnostics reproduce through the existing native tools/Lefthook policy.
- The archived web crate fails Cargo manifest parsing because inherited workspace
  dependencies such as `jarkup-rs` were removed. Its tasks stay outside normal gates.
- In `engineering-standard`, pnpm 12.4.1 automatically ran dependency installation
  during `pnpm exec`, independently of mise's auto-install setting. Setting
  `verifyDepsBeforeRun: false` makes dependency provisioning explicit here too.

## Reproduce task-contract probes

After provisioning the three repositories and this repository:

```sh
mise exec -- python evals/mise/verify-migrations.py
```

Use `--repositories-root <directory>` for a different sibling layout and
`--temp-dir <directory>` to choose temporary storage. The script copies task
configuration into disposable Git repositories with spaces in their paths. It
replaces Cargo, pnpm, uv, AWS, Docker, and Terraform with recording stubs and checks:

- All six Lambda deployment translations, including missing/invalid stages and
  build failures stopping deployment.
- The publisher's timeout/payload and AgentCore's stage/tag forwarding, timestamp
  default, build/push/apply ordering, and failures stopping subsequent operations.
- Frontend stage environment and build/upload/invalidation ordering.
- Coverage instrumentation/report ordering and original output directories.
- Repeated file arguments with spaces from subdirectories and nonzero exits.
- Generated Git hooks launching through mise with a minimal, unactivated PATH.

The probes verify orchestration; the native project commands in the results table
verify actual tools and application behavior.
