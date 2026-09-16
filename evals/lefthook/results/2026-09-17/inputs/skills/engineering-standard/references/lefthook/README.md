# Lefthook

Use Lefthook's [custom hooks](https://lefthook.dev/configuration/Hook/) as the repository's unified execution interface. Define project-specific formatters and linters directly in `lefthook.yml`; use existing package managers and toolchains to provision them.

The [consolidated upstream documentation](upstream/README.md) provides the full Lefthook v2.1.14 reference in four topic files: [installation](upstream/getting-started.md), [configuration](upstream/configuration.md), [CLI and runtime behavior](upstream/usage.md), and [examples](upstream/examples.md).

## Command contracts

| Hook        | Responsibility                                                    | Changes source files? |
| ----------- | ----------------------------------------------------------------- | --------------------- |
| `lint`      | Run the configured linters without automatic fixes                | No                    |
| `fmt`       | Apply the configured formatting or explicitly chosen fixer policy | Yes                   |
| `fmt-check` | Verify the same formatting policy and file scope as `fmt`         | No                    |
| `check`     | Run `lint`, `fmt-check`, and configured project-level gates       | No                    |

Type checking and any additional validation belong in `check`. Tests may be included according to project policy. Optional means selected in the configuration: every configured gate must propagate failures. Build caches are compatible with the source-read-only contract.

## File selection

Give each leaf hook an explicit default, normally `files: git ls-files`. A bare invocation then selects tracked files. Support repeated `--file` arguments for a targeted selection, including existing untracked files, and `--all-files` for tracked repository files:

```sh
pnpm exec lefthook run fmt --file "src/changed.ts" --file "docs/Release Notes.md"
pnpm exec lefthook run fmt-check --file "src/changed.ts" --file "docs/Release Notes.md"
pnpm exec lefthook run lint --file "src/changed.ts" --file "docs/Release Notes.md"
pnpm exec lefthook run check
```

Use the repository's documented Lefthook executable. Paths should be relative to the Git root. Do not issue an empty targeted invocation: that selects the default scope. Excluded and nonmatching paths can produce successful skips; verify that expected jobs actually ran. Check that targeted paths exist: a missing path that matches a job can reach the native tool and fail instead of skipping.

- Set `root:` for project-specific working directories. Globs remain repository-root-relative; file arguments are made relative to the job's root.
- Define defaults for custom hooks explicitly, including project-scoped commands without `{files}`. The automatic staged/push-file selection of Git hooks is not a general custom-hook contract.
- `--file` selects applicable jobs. Compilers and project-scoped linters still analyze their configured project; document that scope and include relevant manifest/configuration triggers.
- Pin and verify the glob matcher. With the default matcher, `**` requires at least one directory; use paired top-level/nested patterns where needed. Use `glob_matcher: doublestar` only with a version verified to support it, and recheck all inclusions and exclusions.

## Aggregate checks

Make `check` a project-wide entry point. Child Lefthook processes do not inherit the outer process's file selection, so call the leaf hooks explicitly with `--all-files`:

```yaml
check:
  parallel: true
  jobs:
    - name: lint
      run: pnpm exec lefthook run lint --all-files
    - name: fmt-check
      run: pnpm exec lefthook run fmt-check --all-files
    # Add this project's type checks and other read-only gates here.
```

Use the leaf hooks for targeted runs; do not advertise `check --file` as a scoped aggregate. Changes to shared configuration, manifests, or dependencies warrant the full gate, because checking only the changed configuration file can skip affected source files.

Run independent read-only jobs in parallel. Avoid concurrent formatters writing the same files. Share roots, patterns, exclusions, and tool options with YAML anchors where useful; keep the write/check command difference explicit. See the [formatting reference](../formatting/README.md) for native tool pairs and editor behavior.

## Git hooks and output

Keep `pre-commit` fast and explicitly staged-file-scoped. Use `stage_fixed: true` only there, and reuse the selected formatter policies. Verify partially staged files in a disposable repository: formatted staged content should enter the index while unrelated unstaged content stays outside it. A workspace-wide formatter can also modify files that are not staged.

Show a concise summary of successful and failed jobs, plus skipped-job explanations, with the top-level [`output`](https://lefthook.dev/configuration/output/) option:

```yaml
output:
  - summary
  - success
  - failure
  - skips
```

Failed commands print their output and return a nonzero exit status. Successful commands' detailed output is suppressed; add `execution_out` when their stdout/stderr, including non-failing warnings, is needed. Git's and the package manager's own output are controlled separately.

Use `LEFTHOOK_OUTPUT=false` for an explicitly quiet invocation, such as an agent integration that needs only failures. With pnpm scripts, `--silent` also suppresses the script header:

```sh
LEFTHOOK_OUTPUT=false pnpm --silent check
```

Configuration changes can produce a one-time `sync hooks` message; run the repository's hook-install command before verifying output, or use `--no-auto-install` for isolated verification. Check skipped-job explanations when files were expected to match.

## Verification

Validate and inspect the resolved configuration with `lefthook validate` and `lefthook dump`. Exercise actual commands on representative files, including root-level/nested paths, spaces, explicit untracked files, exclusions, and empty selections. Check formatter idempotence, read-only check behavior, failure propagation through `check`, and correct project context. Report existing repository failures separately from hook-routing failures.

The [verified example](lefthook.example.yml) uses `46ki75/internal`'s layout and tool choices. Adapt its paths, exclusions, and gates to the target project. The [evaluations](../../../../evals/lefthook/README.md) cover a disposable guide-derived fixture on Lefthook 2.1.14 and the earlier `internal` integration, including its existing source-quality failures.

Primary references: [file selection and CLI overrides](https://lefthook.dev/usage/commands/run/), [files](https://lefthook.dev/configuration/files-global/), [globs](https://lefthook.dev/configuration/glob/), [root](https://lefthook.dev/configuration/root/), and [stage_fixed](https://lefthook.dev/configuration/stage_fixed/).
