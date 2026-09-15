"""Six frozen, paired omission controls; validation and summarization are offline."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import difflib
import json
from pathlib import Path
import random

if __package__:
    from . import judging, run, structured
else:
    import judging
    import run
    import structured


HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / "results/calibration-2026-09-15-v2/writers"
NAMES = {
    "M": "mica-render-timeout-reference",
    "Q": "quarry-relay-stalled-lane",
    "F": "fallow-cache-independent-procedures",
}
TEMPLATE = "`template_id` selects the stored layout."
RECORD = "`record_id` selects the data rendered into that layout."
MEANINGS = (
    "The template identifier selects the stored layout; the record identifier "
    "selects the data rendered into that layout."
)
# Witnesses verify the mutations offline. They are never included in judge inputs.
# Each row is ID suffix | one required proposition | preserved candidate witness.
ATOMS = {
    "M": """TEMPLATE-MEANING|template_id selects the stored layout.|`template_id` selects the stored layout.
RECORD-MEANING|record_id selects the data rendered into the stored layout.|`record_id` selects the data rendered into that layout.
ENDPOINT|The rendering endpoint is POST /v2/render.|Send `POST /v2/render`
REQUEST-TYPE|Requests use Content-Type: application/json.|Content-Type: application/json
AUTH-SCOPE|The bearer token requires render:write scope.|The token requires the `render:write` scope.
TEMPLATE-TYPE|template_id is a required string field.|exactly two required string fields, `template_id` and `record_id`
RECORD-TYPE|record_id is a required string field.|exactly two required string fields, `template_id` and `record_id`
SUCCESS-BODY|A successful response contains PDF bytes.|and the PDF bytes as the body.
TIMEOUT-DEFAULT|render_timeout_ms defaults to 15000 milliseconds.|`render_timeout_ms` | 15000 milliseconds
TIMEOUT-CEILING|The configured render_timeout_ms is the maximum request deadline.|A request can shorten the configured deadline but cannot extend it.
ABSENT-HEADER|An absent timeout header uses the configured render_timeout_ms.|If the header is absent, the effective timeout is the configured `render_timeout_ms`.
SHORT-EXAMPLE|With render_timeout_ms=15000, header 8000 selects eight seconds.|`X-Mica-Timeout-Ms: 8000` | Uses an eight-second deadline
LONG-EXAMPLE|With render_timeout_ms=15000, header 45000 is rejected with timeout_exceeds_limit.|`X-Mica-Timeout-Ms: 45000` | Returns HTTP 400 with `{"error":"timeout_exceeds_limit"}`
RELOAD-INVALID|An invalid reload retains the previous settings.|An invalid file produces a nonzero exit and retains the previous settings.
INFLIGHT-UNKNOWN|Timeout behavior for requests already rendering during hot reload is undocumented.|**Timeout behavior for requests already rendering during a hot reload is undocumented.**
DRAIN-PRACTICE|When predictable timing matters, drain active renders before reloading a changed timeout.|When predictable timing matters, drain active renders before reloading a changed timeout.""",
    "Q": """RATE-UNIT|Resume --rate 120 means exactly 120 events per second, not a count or duration.|The rate is exactly **120 events per second**, not an event count or a duration.
CHECKPOINT-RETENTION|Retain the checkpoint until incident closure.|Retain it until the incident is closed.
TARGET|Recovery is scoped to invoices-eu.|Use this runbook only for **invoices-eu**
TOKEN-MODE|The operations token file must have mode 0600 before mutation.|`/etc/quarry/ops-token` is readable by your session and has mode **0600**.
FREE-SPACE|The spool filesystem requires at least 8 GiB free before mutation.|The filesystem containing `/var/lib/quarry/invoices-eu` has at least **8 GiB free**.
OWNER-TYPE|The starting lease_owner is the string none, not JSON null.|`"none"` — a string, not JSON `null`
PAUSE-STATE|Pause must report state=paused before checkpoint or reset.|report `state=paused`** before checkpoint or reset.
PAUSE-PAYLOADS|Pausing retains queued payloads.|Pausing stops new lease grants and retains all queued payloads.
CHECKPOINT-OFFSET|Checkpoint exports the current committed offset.|The checkpoint exports only the current committed offset.
CHECKPOINT-NOT-BACKUP|The checkpoint is not a payload or spool backup.|**It does not copy payloads and is not a spool backup.**
OWNER-GUARD|If an active owner appears, --expect-owner none makes reset fail without mutation.|`--expect-owner none` is a concurrency guard: if an active owner appears, the command fails without mutation.
RESET-NO-REPLAY|Reset does not request replay.|It does not change the committed offset or request replay.
PENDING-ACCEPTANCE|Acceptance requires pending below the original captured count.|`pending` | Lower than the original captured `pending`
DUPLICATE-ACCEPTANCE|Acceptance requires duplicate_acks=0.|`duplicate_acks` | Equal to `0`
LATENCY-ACCEPTANCE|Acceptance requires p95_ack_ms at most 800 milliseconds.|`p95_ack_ms` | At most `800` milliseconds
CONTAINMENT-ONCE|On resume failure or failed acceptance, attempt the containment pause once.|If resume fails or recovery does not pass acceptance, run this command **once**:""",
    "F": """CATALOG-LIMIT-UNIT|The catalog warm --limit 200 means 200 catalog entries, not a request rate.|The limit is 200 catalog entries, not a request rate.
PRICING-POPULATION-SOURCE|Incoming preview requests populate pricing-preview.|Let incoming preview requests populate the cache.
CATALOG-HOST|The catalog-search procedure independently states execution on cache-admin-02.|Work on `cache-admin-02` with an active production-scoped `cache-maintainer` session
PRICING-HOST|The pricing-preview procedure independently states execution on cache-admin-02.|Work on `cache-admin-02` with an active production-scoped `cache-maintainer` session
CATALOG-ALL-WARNING|The catalog-search procedure independently prohibits --all because it clears every cache in the tenant.|Never use `--all`; it clears every cache in the selected tenant.
PRICING-ALL-WARNING|The pricing-preview procedure independently prohibits --all because it clears every cache in the tenant.|Never use `--all`; it clears every cache in the selected tenant.
CATALOG-GUARD|The catalog clear uses --if-schema catalog-18.|fallow cache clear --tenant cedar-shop --cache catalog-search --if-schema catalog-18
CATALOG-MISMATCH|The catalog schema guard makes no changes on mismatch.|A mismatch exits 3 without changes.
CATALOG-WARM-GATE|Catalog warming must succeed before observation.|Proceed only if warming succeeds.
CATALOG-READY|Catalog acceptance requires ready=true.|Require both `ready=true` and `miss_ratio` at most 0.05.
CATALOG-MISS-RATIO|Catalog acceptance requires miss_ratio at most 0.05.|Require both `ready=true` and `miss_ratio` at most 0.05.
PRICING-GUARD|The pricing clear uses --if-tax-revision tax-2026-09.|fallow cache clear --tenant cedar-shop --cache pricing-preview --if-tax-revision tax-2026-09
PRICING-NO-WARM|The warm command is unsupported for pricing-preview.|The `warm` command is unsupported for `pricing-preview`; do not apply the catalog warming step here.
PRICING-WINDOW|Pricing observation uses a two-minute window.|fallow cache observe --tenant cedar-shop --cache pricing-preview --window 2m --json
PRICING-READY|Pricing acceptance requires ready=true.|Require both `ready=true` and `max_quote_age_s` at most 30.
PRICING-AGE|Pricing acceptance requires max_quote_age_s at most 30.|Require both `ready=true` and `max_quote_age_s` at most 30.""",
}
DELETIONS = {
    "M1": ("TEMPLATE-MEANING", [TEMPLATE + " "]),
    "M2": ("RECORD-MEANING", [" " + RECORD]),
    "Q1": (
        "RATE-UNIT",
        [
            "The rate is exactly **120 events per second**, not an event count or a duration.\n\n"
        ],
    ),
    "Q2": (
        "CHECKPOINT-RETENTION",
        [
            " Retain it until the incident is closed.",
            " Retain the checkpoint until incident closure.",
        ],
    ),
    "F1": (
        "CATALOG-LIMIT-UNIT",
        ["The limit is 200 catalog entries, not a request rate. "],
    ),
    "F2": (
        "PRICING-POPULATION-SOURCE",
        ["Let incoming preview requests populate the cache. "],
    ),
}
STATUSES = ("valid", "transport_error", "schema_error", "evidence_error", "missing")


def encoded(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    )


def fingerprint(value):
    return run.digest(encoded(value))


def save(path, value):
    Path(path).write_text(encoded(value), encoding="utf-8")


def build_manifest():
    controls, hashes = [], {}
    for base, name in NAMES.items():
        fixture = HERE / "cases/calibration" / (name + ".json")
        original = run.read_json(fixture)
        donor = (
            fixture
            if base == "F"
            else ARCHIVE / ("calibration-" + name + "-B/output.md")
        )
        preserved = (
            original["draft"] if base == "F" else donor.read_bytes().decode("utf-8")
        )
        source = original["source_facts"]
        if base == "M":
            if (
                MEANINGS not in original["draft"]
                or preserved.count("Success returns HTTP 200") != 1
            ):
                raise ValueError("Mica baseline/provenance changed")
            preserved = preserved.replace(
                "Success returns HTTP 200",
                TEMPLATE + " " + RECORD + "\n\nSuccess returns HTTP 200",
            )
            source += (
                "\n\nField-meaning provenance: original draft, Endpoint and authentication: "
                + MEANINGS
            )
        prefix = {"M": "R-MICA-", "Q": "R-QR-", "F": "R-FALLOW-"}[base]
        atoms = [line.split("|", 2) for line in ATOMS[base].splitlines()]
        requirements = [
            {"id": prefix + ident, "description": description}
            for ident, description, _ in atoms
        ]
        witnesses = {prefix + ident: quote for ident, _, quote in atoms}
        case = {
            "task": "Assess the two documents against the source facts and every supplied atomic requirement.",
            "source_facts": source,
            "draft": preserved,
            "requirements": requirements,
            "issues": [],
        }
        for ident, (target, deletions) in DELETIONS.items():
            if ident[0] != base:
                continue
            omitted = preserved
            for deletion in deletions:
                if omitted.count(deletion) != 1:
                    raise ValueError("Deletion is not unique: " + ident)
                omitted = omitted.replace(deletion, "", 1)
            target = prefix + target
            for atom, quote in witnesses.items():
                if quote not in preserved or (quote in omitted) != (atom != target):
                    raise ValueError("Unexpected fact mutation: " + ident + ":" + atom)
            if any(deletion.strip() in omitted for deletion in deletions):
                raise ValueError("Deleted fact remains: " + ident)
            checks = {
                role: run.check_output(original, text)
                for role, text in (("preserved", preserved), ("omitted", omitted))
            }
            if not 12 <= len(requirements) <= 18 or any(
                not check["passed"] for values in checks.values() for check in values
            ):
                raise ValueError("Control complexity or preservation check failed")
            expected: dict = {
                role: {
                    atom: "fail" if role == "omitted" and atom == target else "pass"
                    for atom in witnesses
                }
                for role in ("preserved", "omitted")
            }
            expected["winner"] = "preserved"
            controls.append(
                {
                    "id": ident,
                    "target": target,
                    "case": case,
                    "omitted": omitted,
                    "deletions": deletions,
                    "witnesses": witnesses,
                    "expected": expected,
                    "schema": judging.schema_for(case),
                    "checks": checks,
                    "diff": "".join(
                        difflib.unified_diff(
                            preserved.splitlines(True),
                            omitted.splitlines(True),
                            fromfile="preserved",
                            tofile="omitted",
                        )
                    ),
                    "hashes": {
                        "preserved": run.digest(preserved),
                        "omitted": run.digest(omitted),
                        "expected": fingerprint(expected),
                    },
                }
            )
        for path in (fixture, donor):
            hashes[str(path.relative_to(HERE))] = run.digest(
                path.read_bytes().decode("utf-8")
            )
    for name in ("controls.py", "run.py", "judging.py", "structured.py"):
        hashes[name] = run.digest((HERE / name).read_bytes().decode("utf-8"))
    jobs = [
        {"id": c["id"] + "-" + order, "control": c["id"], "order": order}
        for c in controls
        for order in ("PN", "NP")
    ]
    random.Random(46077).shuffle(jobs)
    return {
        "version": 1,
        "system": judging.system_prompt(),
        "model": run.JUDGE_MODEL,
        "variant": "high",
        "timeout": 600,
        "source_hashes": hashes,
        "controls": controls,
        "jobs": jobs,
    }


def inputs(control, order):
    texts = {"P": control["case"]["draft"], "N": control["omitted"]}
    return {
        **control["case"],
        "candidates": dict(zip(("left", "right"), (texts[letter] for letter in order))),
    }


def row(job, status, failures=()):
    return {
        "trial_id": job["id"],
        "control_id": job["control"],
        "order": job["order"],
        "status": status,
        "failures": list(failures),
        "requirements": None,
        "regressions": None,
        "winner": None,
    }


def assess(job, control, value):
    documents = inputs(control, job["order"])["candidates"]
    try:
        judging.validate(value, control["case"], documents["left"], documents["right"])
    except (ValueError, KeyError, TypeError) as error:
        # The shared validator exposes ValueError rather than typed error stages.
        evidence_errors = {
            "Passing requirement lacks candidate evidence",
            "Evidence quote is not an exact candidate substring",
        }
        return row(
            job,
            "evidence_error" if str(error) in evidence_errors else "schema_error",
            [str(error)],
        )
    result = row(job, "valid")
    mapping = dict(
        zip(
            ("left", "right"),
            ("preserved" if c == "P" else "omitted" for c in job["order"]),
        )
    )
    result["requirements"] = {
        mapping[side]: {
            key: item["status"] for key, item in candidate["requirements"].items()
        }
        for side, candidate in value["candidates"].items()
    }
    result["regressions"] = {
        mapping[side]: len(candidate["regressions"])
        for side, candidate in value["candidates"].items()
    }
    result["winner"] = mapping.get(value["winner"], value["winner"])
    return result


def trial(output, manifest, job):
    control = next(c for c in manifest["controls"] if c["id"] == job["control"])
    folder = output / "trials" / job["id"]
    folder.mkdir(parents=True)
    save(
        folder / "attempt.json",
        {
            "attempt": 1,
            "job": job,
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    try:
        native, value = structured.call_structured(
            folder / "native",
            manifest["system"],
            encoded(inputs(control, job["order"])),
            control["schema"],
            model=manifest["model"],
            variant=manifest["variant"],
            timeout=manifest["timeout"],
        )
    except Exception as error:
        result = row(
            job, "transport_error", ["Transport exception: " + type(error).__name__]
        )
    else:
        if value is not None:
            save(folder / "judgment.json", value)
        result = (
            assess(job, control, value)
            if native["status"] == "completed"
            else row(job, "transport_error", native["failures"])
        )
    save(folder / "assessment.json", result)
    return result


def collect(output, manifest):
    rows = []
    for job in manifest["jobs"]:
        folder = output / "trials" / job["id"]
        path = folder / "assessment.json"
        item = (
            run.read_json(path)
            if path.exists()
            else row(
                job,
                "transport_error" if folder.exists() else "missing",
                ["Incomplete attempt"] if folder.exists() else [],
            )
        )
        if (
            any(
                item[key] != expected
                for key, expected in (
                    ("trial_id", job["id"]),
                    ("control_id", job["control"]),
                    ("order", job["order"]),
                )
            )
            or item["status"] not in STATUSES
        ):
            raise ValueError("Invalid saved trial metadata")
        rows.append(item)
    return rows


def rate(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def summarize(manifest, rows):
    controls = {c["id"]: c for c in manifest["controls"]}
    valid = [r for r in rows if r["status"] == "valid"]
    counts = {status: sum(r["status"] == status for r in rows) for status in STATUSES}
    planned, attempted, count = (
        len(manifest["jobs"]),
        len(rows) - counts["missing"],
        len(valid),
    )

    def targets(item):
        target = controls[item["control_id"]]["target"]
        return tuple(
            item["requirements"][role][target] for role in ("preserved", "omitted")
        )

    pairs = [targets(r) for r in valid]
    success = sum(pair == ("pass", "fail") for pair in pairs)
    untouched = Counter(
        status
        for r in valid
        for values in r["requirements"].values()
        for atom, status in values.items()
        if atom != controls[r["control_id"]]["target"]
    )
    metrics = {
        "response_failure": rate(attempted - count, attempted),
        "valid_response": rate(count, planned),
        "omission_detection": rate(sum(n == "fail" for p, n in pairs), count),
        "omission_false_pass": rate(sum(n == "pass" for p, n in pairs), count),
        "preserved_false_fail": rate(sum(p == "fail" for p, n in pairs), count),
        "paired_semantic_success": rate(success, count),
        "end_to_end_success": rate(success, planned),
        "preserved_regression_flags": rate(
            sum(r["regressions"]["preserved"] > 0 for r in valid), count
        ),
    }
    for index, role in enumerate(("preserved", "omitted")):
        metrics[role + "_uncertain"] = rate(
            sum(pair[index] == "uncertain" for pair in pairs), count
        )
    for status in ("pass", "fail", "uncertain"):
        metrics["untouched_" + status] = rate(
            untouched[status], sum(untouched.values())
        )
    for winner in ("preserved", "omitted", "tie", "uncertain"):
        metrics["winner_" + winner] = rate(
            sum(r["winner"] == winner for r in valid), count
        )
    swaps = []
    for ident in controls:
        orders = [r for r in valid if r["control_id"] == ident]
        complete = len(orders) == 2
        swaps.append(
            {
                "control_id": ident,
                "eligible": complete,
                "winner_agrees": orders[0]["winner"] == orders[1]["winner"]
                if complete
                else None,
                "target_agrees": targets(orders[0]) == targets(orders[1])
                if complete
                else None,
                "decisive_reversal": {r["winner"] for r in orders}
                == {"preserved", "omitted"}
                if complete
                else None,
                "both_orders_target_success": all(
                    targets(r) == ("pass", "fail") for r in orders
                )
                if complete
                else None,
            }
        )
    eligible = sum(s["eligible"] for s in swaps)
    metrics["swap_eligible"] = rate(eligible, len(controls))
    for key in ("winner_agrees", "target_agrees", "decisive_reversal"):
        metrics["swap_" + key] = rate(sum(s[key] is True for s in swaps), eligible)
    metrics["swap_winner_disagrees"] = rate(
        sum(s["winner_agrees"] is False for s in swaps), eligible
    )
    metrics["both_orders_target_success"] = rate(
        sum(s["both_orders_target_success"] is True for s in swaps), len(controls)
    )
    return {
        "schema_version": 1,
        "manifest_sha256": fingerprint(manifest),
        "planned_trial_ids": [j["id"] for j in manifest["jobs"]],
        "counts": counts,
        "trials": rows,
        "metrics": metrics,
        "swaps": swaps,
    }


def execute(output, manifest, concurrency):
    output.mkdir()  # A new directory prevents accidental overwrites and retries.
    save(
        output / "manifest.json",
        {"sha256": fingerprint(manifest), "manifest": manifest},
    )
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        list(pool.map(lambda job: trial(output, manifest, job), manifest["jobs"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--concurrency", type=int, default=3)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--summarize", action="store_true")
    args = parser.parse_args(argv)
    if args.concurrency < 1 or (not args.validate_only and args.output is None):
        parser.error("Positive concurrency and --output are required for run/summarize")
    if args.validate_only:
        manifest = build_manifest()
        print(
            encoded(
                {
                    "controls": len(manifest["controls"]),
                    "planned_calls": len(manifest["jobs"]),
                    "atoms_per_control": {
                        c["id"]: len(c["case"]["requirements"])
                        for c in manifest["controls"]
                    },
                    "omitted_proxy_checks_passed": sum(
                        len(c["checks"]["omitted"]) for c in manifest["controls"]
                    ),
                }
            ),
            end="",
        )
        return 0
    if args.summarize:
        frozen = run.read_json(args.output / "manifest.json")
        manifest = frozen["manifest"]
        if frozen["sha256"] != fingerprint(manifest):
            raise ValueError("Frozen manifest hash mismatch")
    else:
        manifest = build_manifest()
        execute(args.output, manifest, args.concurrency)
    report = summarize(manifest, collect(args.output, manifest))
    save(args.output / "summary.json", report)
    print(encoded(report), end="")
    return int(report["counts"]["valid"] != len(manifest["jobs"]))


if __name__ == "__main__":
    raise SystemExit(main())
