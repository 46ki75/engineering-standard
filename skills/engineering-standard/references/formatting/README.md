# Project-specific formatting

Expose formatting through [mise tasks](../mise/README.md), with file selection and native formatter commands in `lefthook.yml`. Keep formatting rules in their native configuration files and provision pinned tools through the project's toolchain and package managers. The [Lefthook reference](../lefthook/README.md) defines selection and hook behavior.

## Formatter contract

- Give `fmt` and `fmt-check` identical roots, file patterns, exclusions, tool versions, and configuration discovery. Only their write/check modes should differ.
- Format the affected, covered files and verify the same selection with `fmt-check`. Save buffers first; a successful disk check does not verify unsaved changes.
- Confirm that deliberately unformatted input changes, a second format is stable, and `fmt-check` fails before formatting and passes afterward without changing source files.
- Preserve generated files, ignored paths, unrelated edits, and partial staging. Treat an unexpected empty selection as a routing problem, even if Lefthook exits successfully.
- Resolve project-local executables from the appropriate package root. Provision dependencies before running hooks; formatting a file should not update lockfiles or install tools.

Typical native command pairs, with file selection supplied by Lefthook:

| Tool          | `fmt`                                           | `fmt-check`                                             |
| ------------- | ----------------------------------------------- | ------------------------------------------------------- |
| Prettier      | `pnpm exec prettier --write {files}`            | `pnpm exec prettier --check {files}`                    |
| Ruff          | `uv run --locked --no-sync ruff format {files}` | `uv run --locked --no-sync ruff format --check {files}` |
| Cargo/rustfmt | `cargo fmt --all`                               | `cargo fmt --all -- --check`                            |
| Terraform     | `terraform fmt {files}`                         | `terraform fmt -check {files}`                          |

These are command patterns, not a universal tool list. Use the repository's package manager and supported CLI versions. Terraform's provider lockfile does not pin the Terraform CLI.

### Scope and project context

`cargo fmt --all` uses Cargo metadata, including each crate's edition, but formats the whole workspace even when one Rust file triggered the job. Document that wider scope and verify it is acceptable before running it in a dirty worktree. Do not replace it with a hardcoded edition unless that is the project's explicit policy.

Working directories affect executable resolution and ignore-file discovery. For example, run web-package Prettier jobs from that package's root. Mirror necessary exclusions in Lefthook when a tool's explicit-file interface bypasses its normal discovery or ignore rules.

If a project deliberately uses a linter's fixer as its formatting policy, document the overlap. For example, `markdownlint-cli2 --fix` can leave unfixable lint errors, and the read-only `markdownlint-cli2` command can serve both `lint` and `fmt-check`. Do not silently substitute a different Markdown formatter.

## Editors and agent hooks

Use the same native formatter, version, configuration, and ignore context in the editor. Select one formatting owner per language and verify actual saves using unsaved buffer content. A CLI-only result does not establish editor parity.

Lefthook operates on filesystem paths; it is not an LSP server or a stdin-to-stdout editor formatter. Use the editor's native formatter integration for buffer formatting. An agent's after-write hook can run `mise run fmt --file <repo-relative-path>`, followed by `fmt-check` and `lint` tasks on the same scope. Normalize absolute paths before passing them to repository-relative globs.

A nonblocking save hook that suppresses formatting failures still requires explicit validation before completion. Batch changed files into one call per hook. Use the full `check` gate for changes to shared configuration or manifests that can affect otherwise untouched files.

## Earlier evaluation

The [historical dprint reference](dprint.md), [example](dprint.example.json), and [evaluation](../../../../evals/formatting/README.md) retain the evidence for the earlier dprint-based workflow. They are not prerequisites for this direct-tool configuration.
