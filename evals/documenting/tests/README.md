# Offline documentation-runner tests

Run from the repository root with Python 3.9 or later:

```sh
python3 -m unittest discover -s evals/documenting/tests -v
```

The suite uses only the standard library. It reads the actual calibration cases,
prompts, skill, reference, and runner. All generated artifacts live in temporary
directories under this directory and are cleaned up. Runtime creation, subprocess
execution, and network sockets are blocked unless replaced with synthetic test
responses. No tests invoke OpenCode, contact models, or access authentication.

- `test_inputs.py`: real-fixture validation, damaged preservation facts, numeric
  regex boundaries, equivalent units/casing, necessary repetition, JSON fences,
  and A/B/C treatment isolation. Count/presence checks remain semantic proxies.
- `test_judgments.py`: complete ID coverage on both sides, invented/duplicate IDs,
  clean cases, enums, evidence, exact object fields, and integer score boundaries.
- `test_events.py`: source-shaped text/step-finish events, separate token buckets,
  cumulative-snapshot double counting, reasoning removal, failed transports,
  malformed/empty responses, retained partial usage, and exact prompt transport
  through stdin with no positional message.
- `test_calibration.py`: synthetic 9-writer/12-judge scheduling, blinding, swaps,
  resumption, invalid judge retention, failure denominators, budget arithmetic,
  resolved tool permissions, and closed stdin on read-only inspections. Its mocks
  support repeated agent/configuration inspections and verbose model listings;
  unknown commands fail without executing anything.
- `support.py`: isolated runner loading and offline boundaries. It does not create
  runner bytecode outside this directory.

## Remaining limitations

- **Usage visibility:** `observed_model_steps` counts completed step events, not
  every provider attempt. OpenCode can retry internally without emitting retry
  status through the JSON CLI. The runner marks provider attempts unavailable;
  budget projections use reported usage and cannot recover interrupted-attempt
  usage. Reported OAuth cost is not necessarily subscription billing.
- **Runtime evidence:** offline mocks and read-only model metadata cannot prove
  authenticated model availability or the effective provider/authentication
  transforms. Those remain part of the approved host calibration.
- **Scope:** three fixed drafts and single-session finalization do not establish
  efficacy, held-out performance, or normal skill-discovery behavior. Literal,
  regex, and count checks do not establish semantic preservation.

### Primary sources inspected (OpenCode `v1.18.31`)

These links are provenance; the tests do not fetch them.

- [CLI emission and prompt transport](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/opencode/src/cli/cmd/run.ts)
- [Verbose model listing format](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/opencode/src/cli/cmd/models.ts)
- [Flat debug-agent output and resolved tools](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/opencode/src/cli/cmd/debug/agent.handler.ts)
- [Last-match permissions and tool aliases](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/opencode/src/permission/index.ts)
- [Token normalization (`getUsage`)](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/opencode/src/session/session.ts)
- [Step emission and processor retries](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/opencode/src/session/processor.ts)
- [Retry policy](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/opencode/src/session/retry.ts)
- [Effective request settings and variant lookup](https://github.com/anomalyco/opencode/blob/v1.18.31/packages/opencode/src/session/llm/request.ts)

`getUsage` already subtracts reasoning from output and cache reads/writes from
input. The tests preserve those five nonoverlapping buckets without subtracting
them again or adding `tokens.total` or cumulative message snapshots a second time.
