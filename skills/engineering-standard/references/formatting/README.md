# dprint formatting

Use dprint as a repository-defined formatting entry point. Keep style in the selected formatters' existing configuration, and let the repository define covered files and tool versions.

The [evaluation](../../../../evals/formatting/results/2026-09-16/report.md) supports a small, declarative, stdin-only exec configuration. It also found process-lifecycle failures in exec 0.7.3 and interference from existing save actions. The operational rule applies to configured repositories; unconditional adoption of that plugin version has not passed the evaluation gates.

## Configuration contract

1. **Pin and provision tools.** Pin dprint, its plugins, and the delegated formatters through the project's existing dependency/toolchain mechanism. Resolve project-local executables explicitly. Install dependencies before formatting; save operations should not install tools.
2. **Keep commands declarative and source files read-only.** Use stdin for input and stdout exclusively for formatted content. Set `exec.cwd` to `${configDir}` and pass the original absolute filename when the formatter supports it. A file-writing delegate can mutate files even during `dprint check`.
3. **Keep scope explicit.** Configure the intended source trees and exclusions, including generated files. Check both positive and excluded examples. A successful stdin invocation can be a pass-through for an excluded file.
4. **Start with `incremental: false`.** Exec cannot automatically discover every external configuration and executable dependency. Enable incremental formatting only after testing invalidation with the relevant `cacheKeyFiles` and version changes; use `cacheKey` to invalidate changes those files do not capture.
5. **Add scoped configuration only where required.** Rust's stdin interface does not infer a file's Cargo edition or nested rustfmt configuration. A uniform workspace can specify its edition once; a differently configured subtree needs an appropriate scoped dprint configuration.

The [tested example](dprint.example.json) uses `internal`'s directory layout: one configuration, five command mappings, and no formatter adapters. It uses the locked Prettier package, Rust's toolchain file, a previously synchronized uv environment, and Terraform on PATH. Pin the Terraform CLI separately: its provider lockfile does not pin the CLI.

The example's Markdown engine is Prettier, matching the evaluated editor workflow. That is a project policy choice: `internal`'s commit hook instead uses markdownlint fixes. If preserving those fixes is the requirement, the tested alternative command is:

```text
node node_modules/markdownlint-cli2/markdownlint-cli2-bin.mjs --format "{{{file_path}}}"
```

This formats stdin but does not establish that Markdown lint checks pass. Keep the existing lint checks.

### Details that affect correctness

- **Exec 0.7.3 requires triple braces for literal paths:** `"{{{file_path}}}"`. Double braces HTML-escape characters such as `&`. The plugin substitutes arguments after tokenization; the tested triple-brace form preserves spaces, Unicode, and quotes.
- **Match ignore-file context.** Applying the web workspace's `.prettierignore` to Markdown outside that workspace caused a successful no-op. The example therefore has separate web and Markdown mappings.
- **Test actual edits.** Include deliberately unformatted inputs and check that they change. Matching outputs from two no-op invocations does not prove formatting works.
- **Bound automation at the execution layer.** Exec 0.7.3 hung after a child exited by signal, and its timeout/cancellation did not reliably stop that child. Its `timeout` setting is not a process-cleanup guarantee. These failures block an unconditional default recommendation.

## CLI, hooks, and CI

Run from the project context using its documented scripts or pinned executable. For example:

```sh
dprint fmt -- "src/changed.ts" "docs/Release Notes.md"
dprint check -- "src/changed.ts" "docs/Release Notes.md"
```

Use the same covered scope for both commands. In the evaluated CLI, exit `0` indicates success, `20` indicates formatting differences, and `14` indicates no matching files. Investigate an unexpected empty selection. Preserve exclusions and unrelated edits.

If no affected files are covered, report that fact and skip the scoped invocation. An empty argument list would select the whole configured scope.

CI can run `dprint check` over the configured scope. Hooks should propagate failures. Existing hooks that suppress errors still require an explicit final check. With Lefthook, scoped `dprint fmt {staged_files}` and `stage_fixed: true` preserved the tested partially staged file's unstaged edits. `dprint fmt --staged` alone is not evidence of index-preservation behavior.

## Editors

Select dprint as the formatting owner for covered languages and verify saves against the CLI using **unsaved buffer content**. Retain other save actions only after checking their output, order, failures, and repeated-save behavior.

### Neovim / LazyVim

Use Conform's built-in `dprint` formatter, which supplies the absolute filename to `dprint fmt --stdin` and locates the repository configuration. Override the relevant `formatters_by_ft` entries and use `lsp_format = "never"` for the dprint-owned path to avoid an unverified fallback. The tested filetypes included `rust`, `markdown`, `typescript`, `typescriptreact`, `css`, `python`, and **`tf`**.

LazyVim already owns the save callback; configure its Conform options through the existing plugin specification. Adding a second `format_on_save` handler is unnecessary. The existing `markdown-toc` step generated additional content beyond dprint's output, so exact CLI/editor parity requires an explicit decision about that step.

For example, inside the existing Conform plugin specification:

```lua
opts = function(_, opts)
  opts.formatters_by_ft.markdown = { "dprint", lsp_format = "never" }
end
```

### VS Code

Use `dprint.dprint` as `editor.defaultFormatter` for the covered languages, with `editor.formatOnSave` enabled. Override existing language-specific Prettier settings where necessary; check folder and multi-root workspace settings. Resolve the same pinned dprint executable through PATH or the user/profile-level `dprint.path` setting.

The dprint-only profile passed actual saves and external Prettier configuration refresh. The profile with `source.fixAll` restored canceled the first Markdown and CSS saves in the controlled test; a second save succeeded with the buffer intact. A successful formatter call therefore does not substitute for confirming a successful save.

A formatting-only language override can start with:

```json
{
  "[markdown]": {
    "editor.defaultFormatter": "dprint.dprint",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": { "source.fixAll": "never" }
  }
}
```

Apply corresponding overrides to the other covered languages and validate any additional save-time transformations separately.

## Evidence and maintenance

The evaluated configuration matched direct formatters on 283 files. Representative Rust, TSX, and Markdown saves had p95 below 122 ms on the recorded macOS host. Recheck output, scope, failures, and configuration invalidation when upgrading the CLI, plugin, formatter, or editor integration.

Primary references:

- [dprint configuration](https://dprint.dev/config/) and [CLI](https://dprint.dev/cli/)
- [Exec 0.7.3 configuration and implementation](https://github.com/dprint/dprint-plugin-exec/tree/0.7.3)
- [Conform's dprint integration](https://github.com/stevearc/conform.nvim/blob/016802de402556da54c36bd7359b441266b01cdd/lua/conform/formatters/dprint.lua)
- [LazyVim's formatting integration](https://github.com/LazyVim/LazyVim/blob/999700997f72227187d49d8b92667183dc7fc809/lua/lazyvim/plugins/formatting.lua)
- [dprint's VS Code extension](https://github.com/dprint/dprint-vscode)
