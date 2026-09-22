# Rust

Use these defaults for Rust code and project configuration. Project-specific rules
take precedence. Follow the existing [mise](../mise/README.md) and
[formatting](../formatting/README.md) references for tool ownership, task wiring,
and formatting scope.

## Workspace configuration

- Use one edition throughout a workspace. Declare it in `[workspace.package]`
  and inherit it in every member with `edition.workspace = true`. Select an edition
  compatible with the workspace's MSRV; declare the resolver explicitly in virtual
  workspaces.
- Centralize shared dependency versions in `[workspace.dependencies]` and inherit
  them with `workspace = true`. Keep genuinely crate-specific dependencies local.
  Put crate-specific features in the consuming member; workspace dependency
  features are additive.
- Inherit shared package metadata and the baseline lints. For an edition-2024
  workspace, the root manifest contains:

```toml
[workspace]
members = ["crates/*"]
resolver = "3"

[workspace.package]
edition = "2024"

[workspace.lints.rust]
missing_docs = "deny"

[workspace.lints.clippy]
unwrap_used = "deny"
```

Each member's manifest includes:

```toml
[package]
edition.workspace = true

[lints]
workspace = true
```

Document the crate and its public API. Apply the unwrap lint to test code too:
tests can return `Result` and use `?`, or use `expect` with a descriptive test
assumption. Keep lint exceptions narrowly scoped and explain their rationale.

## Toolchain, MSRV, and reproducibility

Pin the Rust compiler to an exact release, including the patch version, in root
`rust-toolchain.toml`. Use that file as the single source of truth for the
development and ordinary CI toolchain, including required components and targets.
Let rustup manage Rust; follow [Native Rust](../mise/README.md#native-rust) for
provisioning and mise integration.

For example, a project choosing Rust 1.93.0 would commit:

```toml
[toolchain]
channel = "1.93.0"
profile = "minimal"
components = ["rustfmt", "clippy"]
```

- Declare `rust-version` for published crates, inheriting it from
  `[workspace.package]` when shared. Verify builds and tests on that minimum
  compiler with the supported feature configurations, including after dependency
  changes.
- Treat MSRV as a compatibility contract. The development compiler pinned in
  `rust-toolchain.toml` may be newer. Changes to the edition or development toolchain
  do not automatically change the declared MSRV.
- Commit the workspace's `Cargo.lock` and use `--locked` for validation. Update
  dependencies deliberately through Cargo so validation cannot silently change
  dependency resolution.

## Validation and test runner

Prefer **cargo-nextest** for unit and integration tests. Pin a prebuilt release
through mise's explicit Aqua backend; this avoids compiling the runner with the
project's potentially older Rust toolchain. A mise shorthand is not required:

```toml
[tool_alias]
cargo-nextest = "aqua:nextest-rs/nextest/cargo-nextest"

[tools]
cargo-nextest = "0.9.145"
```

The version above is an example exact pin. Follow the mise reference for lockfiles
and provisioning. Keep runner configuration in `.config/nextest.toml`.

Expose the following through repository tasks, using `rust:` names in polyglot
repositories. CI invokes the same task definitions:

| Task             | Native command or contract                                       |
| ---------------- | ---------------------------------------------------------------- |
| `rust:fmt`       | `cargo fmt --all`                                                |
| `rust:fmt-check` | `cargo fmt --all -- --check`                                     |
| `rust:lint`      | `cargo clippy --locked --workspace --all-targets -- -D warnings` |
| `rust:test`      | Run nextest, then applicable doctests as described below         |
| `rust:ci`        | Run formatting checks, lint, and tests; propagate failures       |

```sh
cargo nextest run --locked --workspace
# Only when the selected packages contain doctestable library targets:
cargo test --locked --workspace --doc
```

Nextest does not run doctests. For intentionally empty unit/integration suites
(such as doctest-only libraries), add `--no-tests=pass` to nextest so doctests can
run. Keep failures for unexpected empty selections. Match feature selections
between test steps and configure additional feature checks explicitly; use
`--all-features` only when enabling every feature together is supported.

## Test isolation and supporting tools

- Keep ordinary tests hermetic: no credentials or live external services. Use
  stubs, fixtures, and local mock servers. Ordinary tests, including doctests,
  form the test portion of the PR gate.
- Put live tests in a dedicated target such as `tests/live.rs`, mark them with
  `#[ignore = "live: requires ..."]`, and expose an explicit `rust:test:live` task.
  For a target named `live`, use
  `cargo nextest run --locked --workspace --test live --run-ignored only`.
  Run live tests separately through manual or scheduled workflows.
- Prefer independent resources and OS-assigned ports. When tests must share an
  external resource, use nextest test groups to limit concurrency. Nextest runs
  each test in a separate process, so in-process mutexes and `serial_test::serial`
  do not serialize those processes.
- Prefer `cargo-llvm-cov` for coverage; it integrates with nextest. Provision it
  through mise and include `llvm-tools-preview` in `rust-toolchain.toml` when
  collecting coverage.
- Prefer `wiremock` for HTTP dependency tests, with an isolated server per test.
  Use `rstest` when parameterized cases or reusable fixtures reduce repetition.
  Add these crates as development dependencies where needed.

## Errors

Use `Result` for recoverable failures and prefer `thiserror` for descriptive custom
error enums. Preserve underlying error sources with `#[from]` or `#[source]` when
wrapping failures. Propagate recoverable errors; use `expect` only for a genuine
invariant, with a message explaining why it should hold.

## References

- Cargo: [workspaces](https://doc.rust-lang.org/cargo/reference/workspaces.html),
  [MSRV](https://doc.rust-lang.org/cargo/reference/rust-version.html), and
  [lockfiles](https://doc.rust-lang.org/cargo/guide/cargo-toml-vs-cargo-lock.html).
- Lints: [missing_docs](https://doc.rust-lang.org/rustc/lints/listing/allowed-by-default.html#missing-docs)
  and [unwrap_used](https://rust-lang.github.io/rust-clippy/stable/index.html#unwrap_used).
- Nextest: [running tests and doctests](https://nexte.st/docs/running/),
  [test groups](https://nexte.st/docs/configuration/test-groups/),
  [toolchain compatibility](https://nexte.st/docs/stability/#minimum-supported-rust-versions),
  and [coverage](https://nexte.st/docs/integrations/test-coverage/).
- Installation: [mise Aqua backend](https://mise.jdx.dev/dev-tools/backends/aqua.html)
  and [nextest's Aqua entry](https://github.com/aquaproj/aqua-registry/blob/main/pkgs/nextest-rs/nextest/cargo-nextest/registry.yaml).
- Test helpers: [wiremock](https://github.com/LukeMathWalker/wiremock-rs)
  and [rstest](https://github.com/la10736/rstest).
- Errors: [thiserror](https://docs.rs/thiserror/latest/thiserror/).
