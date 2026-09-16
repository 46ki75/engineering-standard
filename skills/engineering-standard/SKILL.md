## Guidelines

- Before making changes, human contributors and AI agents must read and follow the project's contribution guide (`CONTRIBUTING.md` or its existing equivalent), when present, and applicable project- or directory-specific instructions. Project-specific rules take precedence over this skill; use this skill's defaults where the project provides no rule.
- Document shared project-specific contribution rules in `CONTRIBUTING.md`. Link to the contribution guide from both `README.md` and `AGENTS.md`, explicitly stating that humans and agents must read it before making changes. Keep agent-only instructions in `AGENTS.md`.
- Keep answers concise and use American English.
- Prefer direct, deterministic computation, execution, and verification over inference. Use calculators, tests, diagnostics, type checkers, linters, LSP diagnostics, direct execution, measurements, or other reproducible checks when applicable.
- Verify a problem before attempting to fix it, and verify the fix afterward using the same or an equivalent check whenever possible.
- When direct verification is not possible, rely on authoritative primary sources such as official documentation, specifications, and RFCs. Use secondary sources only for discovery or context, and verify their claims against primary sources whenever available.
- Add comments when they preserve information that would be costly to rediscover, such as rationale, constraints, invariants, or externally verified behavior; do not restate the code.
- After creating or updating documentation, review the affected document as a whole before finalizing it. Identify and fix unnecessary repetition, duplicate explanations, and inconsistencies. Address organization before sentence-level wording, and preserve necessary context and technical meaning.
- Use the repository's existing validation commands. When configuring Lefthook, define `lint`, `fmt`, `fmt-check`, and a project-wide `check` with project-specific tools directly in its configuration. Format affected, covered files and verify the same scope; report failures and unexpected empty selections. Follow the [Lefthook reference](references/lefthook/README.md) for execution contracts and the [formatting reference](references/formatting/README.md) for formatter and editor integration.
- Use the [Git](references/git/README.md) and [GitHub](references/github/README.md) defaults.
