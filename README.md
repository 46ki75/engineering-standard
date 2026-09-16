# Engineering standard

Reusable engineering guidelines are in [SKILL.md](skills/engineering-standard/SKILL.md).

## Setup

Use the Node.js, pnpm, and uv versions in `mise.toml`, plus Python 3.12 from `.python-version`. Initialize the local dependencies and register the Git hook:

```sh
pnpm install --frozen-lockfile
uv sync --locked
pnpm hooks:install
```

uv manages a local `.venv` with the pinned Ruff development dependency. The Python runners and tests use the standard library. Hook commands use `uv run --locked --no-sync` so they use the prepared environment; rerun `uv sync --locked` after dependency changes.

## Formatting and validation

`lefthook.yml` defines the repository's native-tool workflow:

| Command          | Purpose                                                                                                                                           |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pnpm lint`      | Ruff lint checks for Python                                                                                                                       |
| `pnpm fmt`       | Ruff formatting for Python; Prettier for TypeScript, JavaScript, Markdown, JSON, and YAML                                                         |
| `pnpm fmt-check` | Read-only verification of the same formatting scope                                                                                               |
| `pnpm check`     | Lint, formatting, TypeScript type checking, offline Node/Python tests, Python lockfile consistency, and retained formatting-evidence verification |

The first three commands select tracked files by default. Pass repeated `--file <repo-relative-path>` arguments to select specific files, including new untracked files:

```sh
pnpm fmt --file scripts/validate-commit-message.ts --file README.md
pnpm fmt-check --file scripts/validate-commit-message.ts --file README.md
pnpm lint --file evals/lefthook/verify.py
```

`check` is project-wide: its nested hooks explicitly use `--all-files`. Frozen evaluation inputs, results, and the hash-verified dprint example are excluded from formatting. The live `internal`-repository evaluation is a separate, explicit operation documented in [evals/lefthook](evals/lefthook/README.md).

Lefthook shows job summaries, successes, failures, and skipped-job explanations by default. Failed commands include their diagnostics. Use these overrides for a quiet run or detailed command output:

```sh
LEFTHOOK_OUTPUT=false pnpm --silent check
LEFTHOOK_OUTPUT=summary,success,failure,skips,execution_out pnpm --silent check
```

The individual test commands are also available:

```sh
pnpm typecheck
pnpm test
uv run --locked --no-sync python -m unittest discover -s tests -p 'test_*.py'
uv run --locked --no-sync python -m unittest discover -s evals/documenting/tests -p 'test_*.py'
```

## Local commit-message validation

The `commit-msg` hook checks the [commit-message format](skills/engineering-standard/references/git/README.md), including a blank line before the body and a non-comment body for breaking changes. Git's editor comments and appended diffs do not count as a body. The hook prints an error and aborts the commit when validation fails. Review determines whether the type is appropriate and the impact and migration explanation is adequate.

The validator and tests are written in TypeScript and executed with `tsx`. Type checking runs separately through `tsc --noEmit`. The tests use Node's built-in test runner and create commits in disposable copies of this repository to verify acceptance, rejection, amendments, and the `--no-verify` bypass. The validator can also be invoked as `pnpm validate:commit <message-file>` in CI.
