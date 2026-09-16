## Engineering principles

- Keep answers concise and use American English.
- Add comments when they preserve information that would be costly to rediscover, such as rationale, constraints, invariants, or externally verified behavior; do not restate the code.
- After creating or updating documentation, review the affected document as a whole before finalizing it. Identify and fix unnecessary repetition, duplicate explanations, and inconsistencies. Address organization before sentence-level wording, and preserve necessary context and technical meaning.
- Prefer direct, deterministic computation, execution, and verification over inference. Use calculators, tests, diagnostics, type checkers, linters, LSP diagnostics, direct execution, measurements, or other reproducible checks when applicable.
- Verify a problem before attempting to fix it, and verify the fix afterward using the same or an equivalent check whenever possible.
- When direct verification is not possible, rely on authoritative primary sources such as official documentation, specifications, and RFCs. Use secondary sources only for discovery or context, and verify their claims against primary sources whenever available.

## Project rules

Project- and directory-specific rules take precedence over this skill's defaults. Before editing, humans and agents must read and follow the project's contribution guide, when present, and applicable local instructions. Respect existing guides under other names or locations.

- `README.md`: Link to the contribution guide and explicitly instruct contributors to read it before making changes.
- `CONTRIBUTING.md`: Define shared project-specific contribution rules for humans and agents. Link to detailed references and tool configurations as needed.
- `AGENTS.md`: Link to the contribution guide and explicitly require agents to read it before making changes. Keep agent-only instructions here.

## Tooling and workflow

- Prefer [mise](references/mise/README.md) for development-tool management and task execution. Pin exact tool releases, including patch versions; keep Rust native in `rust-toolchain.toml`. Declare shared tasks in root `mise.toml`, document commands as `mise run <task>`, and use ecosystem package managers for project dependencies. Keep each tool version and workflow definition authoritative in one place.
- Use the repository's existing validation commands. When adopting mise, expose `lint`, `fmt`, `fmt-check`, and a project-wide `check`; use [Lefthook](references/lefthook/README.md) for Git hooks and file-scoped validation. Format affected, covered files and verify the same scope; report failures and unexpected empty selections. Follow the [formatting reference](references/formatting/README.md) for formatter and editor integration.
- Use the [Git](references/git/README.md) and [GitHub](references/github/README.md) defaults.
