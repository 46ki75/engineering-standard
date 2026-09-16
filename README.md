# Engineering standard

Reusable engineering guidelines are in [SKILL.md](skills/engineering-standard/SKILL.md).

## Setup

Install [mise](https://mise.jdx.dev/installing-mise.html) 2026.9.9 or newer. From the repository root, install the tools locked by `mise.toml` and `mise.lock`, then initialize project dependencies and the Git hook:

```sh
mise trust mise.toml
mise install node pnpm python uv
mise run setup
```

Project-scoped strict locking is enabled in `mise.toml`; explicit tool names keep installation focused on this repository. The lockfile includes macOS arm64 and Linux x64 artifacts. Mise supplies Node.js, pnpm, Python, and uv. uv manages `.venv` and the pinned Ruff development dependency, using mise's Python through `UV_PYTHON`.

Shell activation is optional. Make `mise` available on PATH for terminal, editor, and Git-hook processes. Tasks and hooks use prepared tools and dependencies. Rerun both setup commands after toolchain changes, or just `mise run setup` after dependency changes. `mise tasks ls` lists available tasks.

## Formatting and validation

`mise.toml` defines the task graph; `lefthook.yml` supplies file selection and native formatter/linter commands:

| Command              | Purpose                                                                                                                                           |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `mise run lint`      | Ruff lint checks for Python                                                                                                                       |
| `mise run fmt`       | Ruff formatting for Python; Prettier for TypeScript, JavaScript, Markdown, JSON, and YAML                                                         |
| `mise run fmt-check` | Read-only verification of the same formatting scope                                                                                               |
| `mise run check`     | Lint, formatting, TypeScript type checking, offline Node/Python tests, Python lockfile consistency, and retained formatting-evidence verification |

The first three commands select tracked files by default. Pass repeated `--file <repo-relative-path>` arguments to select specific files, including new untracked files:

```sh
mise run fmt --file scripts/validate-commit-message.ts --file README.md
mise run fmt-check --file scripts/validate-commit-message.ts --file README.md
mise run lint --file evals/lefthook/verify.py
```

Paths are repository-root-relative, even from a subdirectory. `check` is project-wide: its lint and formatting dependencies explicitly use `--all-files`. Frozen evaluation inputs, results, and the hash-verified dprint example are excluded from formatting. The live `internal`-repository evaluation is a separate, explicit operation documented in [evals/lefthook](evals/lefthook/README.md).

Mise labels task output; Lefthook shows job summaries and skipped-job explanations. Failed commands include their diagnostics. For less output or detailed native-tool output:

```sh
LEFTHOOK_OUTPUT=false mise run --quiet --output interleave check
LEFTHOOK_OUTPUT=summary,success,failure,skips,execution_out mise run check
```

The individual test commands are also available:

```sh
mise run typecheck
mise run test
mise run test:node
mise run test:python
mise run test:calibration
```

The existing pnpm scripts are compatibility aliases for mise tasks. CI should install the locked tools and dependencies and run `mise run check` using the same configuration. See the [mise reference](skills/engineering-standard/references/mise/README.md) for the reusable standard and [migration results](evals/mise/README.md) for the elmethis, web, and internal trials.

## Local commit-message validation

The `commit-msg` hook checks the [commit-message format](skills/engineering-standard/references/git/README.md), including a blank line before the body and a non-comment body for breaking changes. Git's editor comments and appended diffs do not count as a body. The hook prints an error and aborts the commit when validation fails. Review determines whether the type is appropriate and the impact and migration explanation is adequate.

The validator and tests are written in TypeScript and executed with `tsx`. Type checking runs separately through `tsc --noEmit`. The tests use Node's built-in test runner and create commits in disposable copies of this repository to verify acceptance, rejection, amendments, and the `--no-verify` bypass. The validator can also be invoked as `mise run validate:commit <message-file>` in CI.
