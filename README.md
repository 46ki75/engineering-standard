# Engineering standard

Reusable engineering guidelines are in [SKILL.md](skills/engineering-standard/SKILL.md).

## Local commit-message validation

Use Node.js 22.13 or newer and pnpm 11.25.0. After cloning, install dependencies and register the hook:

```sh
pnpm install
pnpm hooks:install
```

The hook checks the [commit-message format](skills/engineering-standard/references/git/README.md), including a blank line before the body and a non-comment body for breaking changes. Git's editor comments and appended diffs do not count as a body. The hook prints an error and aborts the commit when validation fails. Review determines whether the type is appropriate and the impact and migration explanation is adequate.

Run the TypeScript checks and integration tests with:

```sh
pnpm typecheck
pnpm test
```

The validator and tests are written in TypeScript and executed with `tsx`. Type checking runs separately through `tsc --noEmit`. The tests use Node's built-in test runner and create commits in disposable copies of this repository to verify acceptance, rejection, amendments, and the `--no-verify` bypass. The validator can also be invoked as `pnpm validate:commit <message-file>` in CI.
