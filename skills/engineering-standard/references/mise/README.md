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

Run routine local tasks as `mise run --silent <task>`. If a task fails, rerun it
without `--silent` to expose the complete diagnostics. CI uses `mise run <task>`
so its logs retain normal task output.

| Task          | Responsibility                                             |
| ------------- | ---------------------------------------------------------- |
| `setup`       | Install locked project dependencies and register hooks     |
| `fmt`         | Apply the project's formatting/fixer policy                |
| `fmt-check`   | Check the same formatting policy and file scope            |
| `lint`        | Run configured linters without fixes                       |
| `test`        | Run the ordinary test suites                               |
| `check:quick` | Provide fast local feedback from a useful subset of checks |
| `check`       | Run the complete project-wide quality gate required by CI  |

Use `check:quick` when a separate fast feedback loop is useful. Target roughly 10
seconds on a normal development environment where practical; this is a guideline,
not a timeout or guarantee. `check` remains authoritative and may depend on
`check:quick` before running slower gates. Tests may be included in `check`
according to project policy. Checks must propagate failures and preserve source
files; generated build artifacts and caches are allowed. Keep credential-dependent
or live tests and deployment operations explicitly named.

In a single-project repository, keep shared tasks in the root catalog. In a
monorepo, let mise own cross-package orchestration instead of relying on recursion
features specific to a package manager or build tool. Mark the root, explicitly list
package configuration roots, and make the root task depend on matching descendant
tasks:

```toml
monorepo_root = true

[monorepo]
config_roots = ["packages/*", "services/*"]

[tasks.check]
depends = ["//...:check"]
```

Each configured package owns the applicable task contract. References beginning
with `:` resolve within that package's configuration root:

```toml
# packages/web/mise.toml
[tasks.check]
depends = [":lint", ":test"]

[tasks.lint]
run = "pnpm exec eslint ."

[tasks.test]
run = "pnpm exec vitest run"
```

The root `mise run check` resolves all matching package tasks in one dependency
graph; it does not spawn nested mise processes. Mise runs each task from its own
configuration root with its layered tools and environment. Use `depends` for these
aggregates so `mise tasks deps check` exposes the graph. Keep required aggregate
patterns nonoptional, and use `mise tasks ls --all` to verify that every intended
package exposes the task. List nested configuration roots explicitly because
`config_roots` supports single-level `*`, not recursive `**`; the `//...:check`
task pattern still matches configured descendants at any depth.

Prefer short TOML tasks; put substantial scripts in file tasks. Describe public
tasks, including side effects such as an image build that also pushes. Keep task
delegation one-way: mise tasks may invoke package-owned scripts or native tools,
but package scripts must not call mise or recursively orchestrate sibling packages.
Omit package-script aliases whose only purpose is to call mise.

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
outside an activated shell. Make mise available on editor/Git PATH. Follow the
[Lefthook reference](../lefthook/README.md) for partial staging.

CI installs the exact mise release, locked tools, and dependencies, then invokes
the same tasks. Update path filters to include configuration, locks, and task
scripts. Keep one definition of each gate; split jobs may invoke its leaf tasks.

Verify task behavior, failure propagation, and hooks without shell activation.
Use disposable repositories and command stubs for deployment checks.

### GitHub Actions

Prefer [jdx/mise-action](https://github.com/jdx/mise-action) to install and cache
mise-managed tools, then run the repository's setup and validation tasks:

```yaml
- uses: actions/checkout@v7
- uses: jdx/mise-action@v4
  with:
    version: "2026.9.9"
- run: mise run setup
- run: mise run check
```

`setup` installs locked project dependencies through their package managers.
Configure package-download caches separately when needed. Use `install_args` to
select job-specific tools while keeping versions in the repository configuration.

See [migration results and reproducible probes](../../../../evals/mise/README.md)
and the [working repository configuration](../../../../mise.toml).
Primary references: [task configuration](https://mise.jdx.dev/tasks/task-configuration.html),
[monorepo tasks](https://mise.jdx.dev/tasks/monorepo.html),
[lockfiles](https://mise.jdx.dev/dev-tools/mise-lock.html),
[package-manager discovery](https://mise.jdx.dev/mise-cookbook/nodejs.html#replacing-corepack),
[pnpm execution settings](https://pnpm.io/settings/build#verifydepsbeforerun),
[rustup overrides](https://rust-lang.github.io/rustup/overrides.html), and
[CI](https://mise.jdx.dev/continuous-integration.html).
