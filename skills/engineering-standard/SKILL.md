## Guidelines

- Keep answers concise and use American English.
- Prefer direct, deterministic computation, execution, and verification over inference. Use calculators, tests, diagnostics, type checkers, linters, LSP diagnostics, direct execution, measurements, or other reproducible checks when applicable.
- Verify a problem before attempting to fix it, and verify the fix afterward using the same or an equivalent check whenever possible.
- When direct verification is not possible, rely on authoritative primary sources such as official documentation, specifications, and RFCs. Use secondary sources only for discovery or context, and verify their claims against primary sources whenever available.
- Add comments when they preserve information that would be costly to rediscover, such as rationale, constraints, invariants, or externally verified behavior; do not restate the code.
- After creating or updating documentation, review the affected document as a whole before finalizing it. Identify and fix unnecessary repetition, duplicate explanations, and inconsistencies. Address organization before sentence-level wording, and preserve necessary context and technical meaning.
- When a repository uses dprint, format affected, covered files with `dprint fmt` and verify the same scope with `dprint check`. Report failures and unexpected empty selections. Follow the [formatting reference](references/formatting/README.md) when configuring integrations.
- Follow project- or repository-specific rules; otherwise, use the [Git](references/git/README.md) and [GitHub](references/github/README.md) defaults.
