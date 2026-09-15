# Recover the invoices-eu delivery lane

Use this runbook only for **invoices-eu** on **relay-07** in cluster **fin-eu**, running Quarry Relay 3.4 with qrelay 3.4.2. It recovers delivery from the existing durable spool.

**Do not pause, reset, resume, or use `receipts-eu` as a recovery test.** It is a distinct reporting lane on the same host.

Keep the incident record open. Execute each step separately and proceed only after its success conditions are met.

## 1. Verify prerequisites

Before any lane mutation, verify all of the following:

- Incident-owner approval has been obtained.
- You are logged in to **relay-07** as **relayops**.
- `qrelay version` reports **3.4.2**.
- `/etc/quarry/ops-token` is readable by your session and has mode **0600**.
- The filesystem containing `/var/lib/quarry/invoices-eu` has at least **8 GiB free**.

The host’s existing client configuration selects `fin-eu` and reads `/etc/quarry/ops-token`. No cluster-selection or token-export command is needed.

**A failed prerequisite blocks recovery. Do not mutate the lane.**

## 2. Capture and validate the starting state

Run:

```sh
qrelay inspect --lane invoices-eu --json
```

Capture all five fields in the incident record before mutation. Continue only if they match:

| Field | Required value |
|---|---|
| `lane` | `"invoices-eu"` |
| `state` | `"stalled"` |
| `spool_health` | `"ok"` |
| `pending` | Greater than zero |
| `lease_owner` | `"none"` — a string, not JSON `null` |

Preserve the original `pending` value for the acceptance comparison.

**Any other combination requires escalation to Queue Reliability without mutation.**

## 3. Pause delivery

Run:

```sh
qrelay pause --lane invoices-eu --wait 45s
```

The command must **exit successfully and report `state=paused`** before checkpoint or reset. Pausing stops new lease grants and retains all queued payloads.

If the command times out, fails, or does not confirm the paused state:

- Stop and escalate to Queue Reliability.
- Do not checkpoint, reset, or resume.
- Record the command result so the receiving operator can distinguish a timeout or failure from a confirmed pause.

## 4. Export the committed offset

After the successful pause, run:

```sh
qrelay checkpoint --lane invoices-eu --out /var/tmp/invoices-eu.before.json
```

Record the checkpoint path and exported committed offset in the incident.

The checkpoint exports only the current committed offset. **It does not copy payloads and is not a spool backup.** Retain it until the incident is closed.

If checkpoint fails, stop and escalate to Queue Reliability. **Do not reset or resume.**

## 5. Clear orphan scheduling metadata

After checkpoint succeeds, run:

```sh
qrelay reset-lease --lane invoices-eu --expect-owner none
```

Reset removes orphan scheduling metadata. It does not change the committed offset or request replay.

`--expect-owner none` is a concurrency guard: if an active owner appears, the command fails without mutation. Never remove the guard to force success.

If reset fails, stop and escalate to Queue Reliability. **Do not resume or retry reset.**

## 6. Resume at the recovery rate

After reset succeeds, run:

```sh
qrelay resume --lane invoices-eu --rate 120
```

The rate is exactly **120 events per second**, not an event count or a duration.

If resume fails, follow [Failure containment and escalation](#failure-containment-and-escalation).

## 7. Verify recovery

After resume succeeds, run:

```sh
qrelay observe --lane invoices-eu --window 5m --json
```

Use the aggregate five-minute result. **All three conditions must pass:**

| Metric | Acceptance condition |
|---|---|
| `pending` | Lower than the original captured `pending` |
| `duplicate_acks` | Equal to `0` |
| `p95_ack_ms` | At most `800` milliseconds |

A shrinking queue alone is insufficient. Record the observation in the incident alongside the starting state, checkpoint path, and committed offset. Retain the checkpoint until incident closure.

If any condition fails, follow the failure procedure below. If observation fails or does not provide the required metrics, acceptance cannot be established; follow the same failure procedure.

## Failure containment and escalation

If resume fails or recovery does not pass acceptance, run this command **once**:

```sh
qrelay pause --lane invoices-eu --wait 45s
```

Then escalate to **Queue Reliability**, reporting:

- The resume failure or acceptance failure.
- The command results and available observation.
- Whether the containment pause exited successfully and reported `state=paused`.

Do not continue recovery after this containment attempt.

## Prohibited recovery actions

Never:

- Delete spool files.
- Edit offsets.
- Restore the checkpoint; there is no documented restoration command in this procedure.
- Retry reset as an improvised recovery.
- Mutate or test against `receipts-eu`.