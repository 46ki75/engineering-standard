# mise

Use mise for development-tool management and shared task execution. Contributors,
agents, CI, and devcontainers use the same repository configuration.
Project-specific rules take precedence.

## Tool ownership and versions

- Declare shared runtimes and standalone CLIs in root `mise.toml`, using **exact
  releases**, including patch versions: `node = "24.21.0"`, `uv = "0.12.15"`.
  Avoid major/minor-only selectors, ranges, `latest`, and `lts`.
  Use explicit backends or `[tool_alias]` for tools absent from the registry.
- Keep one authoritative declaration per tool. For pnpm, an exact
  `package.json#packageManager` pin can be read by mise with
  `idiomatic_version_file_enable_tools = ["pnpm"]` under `[settings]`.
  Verify executable selection with `mise which <command>` and
  `mise exec -- <command> --version`, including inherited global configuration.
- Commit `mise.lock` and generated `.mise/locks/` sidecars. Generate artifacts for
  supported hosts with `mise lock --platform macos-arm64,linux-x64,linux-arm64`.
  Include Linux arm64 when supporting Apple Silicon devcontainers. Exclude
  sidecars from formatting: their exact bytes are hash-verified.
- Set `[tool_config] locked = true` for project-scoped enforcement. Install
  explicit project tool names to avoid provisioning unrelated inherited tools.
  Invocation-wide `--locked` also applies to global tools.
- Set `min_version` to the tested mise compatibility floor; pin the mise release
  exactly in CI and devcontainer bootstrap. These examples were verified with
  mise **2026.9.9**.
- Use ecosystem managers and lockfiles for project dependencies and local CLIs:
  `pnpm install --frozen-lockfile`, `uv sync --locked`, and Cargo's `--locked`.

### Native Rust

Rustup owns Rust. Commit an exact channel, required components, and compilation
targets in **`rust-toolchain.toml`**. Provision with
`rustup toolchain install --no-self-update` from the project root. Include
`llvm-tools-preview` for coverage and the required Lambda cross-compilation target.

Keep rustup's Cargo proxies on PATH. Exclude Rust from mise's selection with
`disable_tools = ["rust"]` under `[settings]`; let mise manage auxiliary CLIs such
as `cargo-lambda` and `cargo-llvm-cov`. A mise-managed Rust toolchain exports
`RUSTUP_TOOLCHAIN`, which overrides the native file. Verify actual selection with
`mise exec -- rustup show active-toolchain`, including inherited environment or
directory overrides.

### Python with uv

Mise supplies the exact interpreter; uv owns `.venv` and its dependencies:

```toml
[env]
UV_PYTHON = { value = "{{ tools.python.path }}", tools = true }
UV_PYTHON_DOWNLOADS = "never"
```

Remove competing development interpreter pins and resync after changing Python.
For a uv workspace, provision all required packages/groups explicitly. Validation
uses prepared dependencies, for example `uv run --locked --no-sync ...`.
Runtime-image requirements are a separate deployment contract.

## Task contracts

| Task        | Responsibility                                                     |
| ----------- | ------------------------------------------------------------------ |
| `setup`     | Install locked project dependencies and register hooks             |
| `fmt`       | Apply the project's formatting/fixer policy                        |
| `fmt-check` | Check the same formatting policy and file scope                    |
| `lint`      | Run configured linters without fixes                               |
| `test`      | Run the ordinary test suites                                       |
| `check`     | Project-wide formatting, lint, type checking, and documented gates |

Tests may be included in `check` according to project policy. Checks must propagate
failures and preserve source files; generated build artifacts and caches are allowed.
Keep credential-dependent/live tests and deployment operations explicitly named.

Use one root task catalog with `<component>:<action>` names and explicit `dir`
values. Prefer short TOML tasks; put substantial scripts in file tasks. Describe
public tasks, including side effects such as an image build that also pushes.

- `depends` schedules independent prerequisites in parallel. Use a `run` array
  for ordered steps; build before deploying and instrument before reporting.
  `mise tasks deps` shows declared dependencies but omits `run` references.
- Define arguments with `usage`; quote shell values such as `"${usage_stage?}"`.
  Pass arguments/environment explicitly to child tasks. Preserve interactive I/O
  for commands such as `terraform apply` using `raw = true`.
- Preserve working directories, defaults, environment, package lifecycle hooks,
  exit status, and output paths when translating Just recipes or package scripts.
  Use `shell = "bash -euo pipefail -c"` under `[task_config]` for Bash pipelines.
- Provision explicitly before running checks. Set `auto_install = false` under
  `[settings]` to disable mise's automatic installation, including shim invocations.
  Disable ecosystem auto-provisioning too: pnpm 11+ defaults to installing before
  `run`/`exec`; use `verifyDepsBeforeRun: false` in `pnpm-workspace.yaml` (or `error`
  to reject stale dependencies). Mise settings do not control package managers.

## Lefthook and CI

Mise owns orchestration; Lefthook owns Git hooks, file selection, and staged-file
handling. Delegate file-scoped tasks with `raw_args = true` and, for example,
`run = "pnpm exec lefthook run fmt --no-auto-install"`. Repeated `--file` arguments
remain repository-root-relative, including when called from a subdirectory.
Keep `check` project-wide; pass `--all-files` to its file-scoped leaves.
An existing Lefthook aggregate may remain authoritative during adoption.

Set `lefthook: mise exec -- pnpm exec lefthook` in `lefthook.yml` for hooks launched
outside an activated shell. Make mise available on editor/Git PATH. Avoid cycles
between mise tasks, package-script aliases, and hooks. Follow the
[Lefthook reference](../lefthook/README.md) for partial staging.

CI installs the exact mise release, locked tools, and dependencies, then invokes
the same tasks. Update path filters to include configuration, locks, and task
scripts. Keep one definition of each gate; split jobs may invoke its leaf tasks.

Verify task behavior, failure propagation, and hooks without shell activation.
Use disposable repositories and command stubs for deployment checks.

See [migration results and reproducible probes](../../../../evals/mise/README.md)
and the [working repository configuration](../../../../mise.toml).
Primary references: [task configuration](https://mise.jdx.dev/tasks/task-configuration.html),
[lockfiles](https://mise.jdx.dev/dev-tools/mise-lock.html),
[package-manager discovery](https://mise.jdx.dev/mise-cookbook/nodejs.html#replacing-corepack),
[pnpm execution settings](https://pnpm.io/settings/build#verifydepsbeforerun),
[rustup overrides](https://rust-lang.github.io/rustup/overrides.html), and
[CI](https://mise.jdx.dev/continuous-integration.html).
