#!/usr/bin/env python3
"""Audit full-v1 artifacts and stored sessions without making inference calls.

Run after writers/judges finish. Partial snapshots report pending/ongoing jobs
and cannot return success. Reports are metadata-only; exports stay in memory.
Live source hashes are opt-in so the frozen run remains auditable after adoption.
Exit codes: 0 verified, 1 mismatch, 2 incomplete, 3 unknown session integrity.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time
import types


sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def import_source(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot import audit dependency")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


full = import_source("_documenting_full_audit_driver", HERE / "full.py")
calibration = import_source("_documenting_full_audit_calibration", HERE / "audit.py")
run = full.base
structured = full.structured_module()
judging = full.judge_module()
ERRORS = calibration.ERRORS + (RecursionError,)
ROLES = ("writers", "judges")
FAILURE_KINDS = {
    None,
    "transport",
    "schema_or_evidence",
    "interrupted",
    "local_failure",
}
SESSION = re.compile(r"ses_[A-Za-z0-9_-]{1,128}")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
HASH = re.compile(r"[a-f0-9]{64}")
text = calibration.text


def check(report, name, passed):
    # Several transports can contribute to one check; a later success must not
    # erase an earlier mismatch in either the verdict or its displayed checks.
    report.setdefault("checks", {})[name] = bool(passed) and report.get(
        "checks", {}
    ).get(name, True)
    if not passed and name not in report["errors"]:
        report["errors"].append(name)


def unknown(report, name):
    """Missing transport evidence is neither a verified input nor a mismatch."""
    if name not in report.setdefault("checks", {}):
        report["checks"][name] = None
    if name not in report.setdefault("unknowns", []):
        report["unknowns"].append(name)


def same(first, second):
    return full.json_hash(first) == full.json_hash(second)


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def guarded(report, name, action):
    try:
        return action()
    except ERRORS as error:
        # Neither decoder errors nor provider/export exceptions are safe to print.
        check(report, name + ":" + type(error).__name__, False)
        return None


def within(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Unsafe artifact path")
    result = root / path
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError("Artifact escapes root")
    return result


def read_events(path):
    events = [
        json.loads(line, object_pairs_hook=structured._unique_object)
        for line in text(path).splitlines()
        if line.strip()
    ]
    full.json_hash(events)  # Reject nonfinite numbers, including float overflow.
    if any(not isinstance(event, dict) for event in events):
        raise ValueError("Invalid event envelope")
    return events


def read_object(path):
    value = full.read_json(path)
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object")
    return value


def session_audit(report, system, prompt, model, variant, session_id):
    """Extend calibration's single export with fork/history checks, thread-safely."""

    def parse(stdout):
        data = calibration.export_json(stdout)
        check(report, "export_not_forked", not data["info"].get("parentID"))
        messages = data["messages"]
        check(
            report,
            "export_fresh_exchange",
            [m["info"].get("role") for m in messages] == ["user", "assistant"],
        )
        provider, model_id = model.split("/", 1)
        users = [m for m in messages if m["info"].get("role") == "user"]
        check(
            report,
            "export_user_configuration",
            len(users) == 1
            and all(
                m["info"].get("agent") == "documentation-eval"
                and m["info"].get("system") is None
                and m["info"].get("model", {}).get("providerID") == provider
                and m["info"].get("model", {}).get("modelID") == model_id
                and all(
                    not p.get("synthetic") and not p.get("ignored") for p in m["parts"]
                )
                for m in users
            ),
        )
        if len(users) == 1:
            check(
                report,
                "export_assistant_parent",
                all(
                    m["info"].get("parentID") == users[0]["info"].get("id")
                    for m in messages
                    if m["info"].get("role") == "assistant"
                ),
            )
        return data

    # A private globals dictionary avoids monkey-patching a parser shared by six
    # workers, and lets calibration own the fresh runtime and read-only CLI call.
    audit = types.FunctionType(
        calibration.session_audit.__code__,
        {**calibration.session_audit.__globals__, "export_json": parse, "check": check},
    )
    try:
        audit(report, system, prompt, model, variant, session_id)
    finally:
        # Persist verdicts, not arbitrary model metadata strings from the export.
        report.pop("assistants", None)
        metadata = report.get("export", {})
        if metadata and (metadata["exit_code"] != 0 or metadata["timed_out"]):
            report["errors"] = [e for e in report["errors"] if e != "export_succeeded"]
            report["checks"].pop("export_succeeded", None)
            unknown(report, "export_succeeded")


def manifest_audit(output, report, check_live_sources, source_root):
    frozen = read_object(output / "manifest.json")
    report["manifest_artifact_sha256"] = full.file_hash(output / "manifest.json")
    check(
        report,
        "manifest_own_hash",
        frozen["manifest_sha256"]
        == full.json_hash({k: v for k, v in frozen.items() if k != "manifest_sha256"}),
    )
    check(
        report,
        "manifest_configuration",
        frozen["format_version"] == full.FORMAT_VERSION
        and frozen["stage"] == "full-blind"
        and type(frozen["max_attempts"]) is int
        and frozen["max_attempts"] in (1, 2)
        and all(
            isinstance(frozen[role + "_model"], str)
            and re.fullmatch(
                r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", frozen[role + "_model"]
            )
            for role in ("writer", "judge")
        )
        and frozen["writer_variant"] == frozen["judge_variant"] == "high"
        and frozen["opencode_version_required"] == run.VERSION
        and frozen["output_token_limit_requested"] == run.TOKEN_LIMIT,
    )
    inputs = frozen["inputs"]
    cases = inputs["cases"]
    metadata = inputs["case_metadata"]
    check(
        report,
        "embedded_cases",
        len({c["id"] for c in cases}) == len(cases)
        and set(metadata) == {c["id"] for c in cases}
        and all(
            metadata[c["id"]]["embedded_sha256"] == full.json_hash(c) for c in cases
        ),
    )
    check(
        report,
        "frozen_schedule",
        same(frozen["jobs"], full.make_schedule(cases, metadata, frozen["seed"])),
    )
    check(
        report,
        "frozen_schema_contract",
        same(
            inputs["judge_schemas"],
            {case["id"]: judging.schema_for(case) for case in cases},
        ),
    )
    # Do not call load_inputs(): it reads live/calibration fixtures and would make
    # post-adoption auditing depend on the current treatment rather than the freeze.
    hashes = {
        **inputs["source_hashes"],
        **{m["source"]: m["source_sha256"] for m in metadata.values()},
    }
    check(
        report,
        "source_hash_metadata",
        bool(hashes)
        and all(
            isinstance(value, str) and HASH.fullmatch(value)
            for value in hashes.values()
        ),
    )
    report["live_sources"] = {"checked": check_live_sources, "files": len(hashes)}
    if check_live_sources:
        for index, (name, expected) in enumerate(sorted(hashes.items())):
            guarded(
                report,
                "live_source_" + str(index),
                lambda n=name, h=expected: check(
                    report,
                    "live_source_" + str(index),
                    full.file_hash(within(source_root, n)) == h,
                ),
            )
    return frozen


def preflight_audit(output, frozen, report):
    ready = full.read_json(output / "ready.json")
    path = within(output, ready["preflight"])
    check(
        report,
        "preflight_freeze",
        ready["manifest_sha256"] == frozen["manifest_sha256"]
        and full.file_hash(path) == ready["preflight_sha256"]
        and ready["writer_variant"] == ready["judge_variant"] == "high",
    )
    full.verify_preflight(full.read_json(path), frozen)
    for role in ("writer", "judge"):
        agent = full.read_json(path.parent / ("preflight-" + role + "-agent.txt"))
        model = frozen[role + "_model"]
        system = (
            frozen["inputs"]["systems"]["A"]
            if role == "writer"
            else frozen["inputs"]["judge_system"]
        )
        check(
            report,
            role + "_preflight_agent",
            agent["name"] == "documentation-eval"
            and agent["prompt"] == system
            and bool(agent["tools"])
            and all(value is False for value in agent["tools"].values())
            and same(
                agent["model"],
                dict(zip(("providerID", "modelID"), model.split("/", 1))),
            ),
        )


def writer_archive_hashes(output):
    """The rejudge.py freeze includes every writer file, including start markers."""
    root = output / "writers"
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Missing local writer archive")
    hashes = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("Unsupported writer archive path")
        if path.is_file():
            hashes[str(path.relative_to(output))] = full.file_hash(path)
    return hashes


def recovery_audit(output, frozen, report, check_live_sources, source_root):
    """Authorize historical writer markers only after proving the complete copy.

    Recovery changes the judge and manifest identity. It does not recreate writer
    invocations: their markers and invocation records belong to the source study.
    A recovery label alone must never grant an exception to origin verification.
    """
    provenance = frozen["recovery"]
    proof = report["recovery"] = {"errors": [], "checks": {}}
    source = Path(provenance["source_output"])
    if not source.is_absolute():
        raise ValueError("Recovery source must be absolute")
    source = source.resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Recovery source overlaps output")
    original_report = {"errors": [], "checks": {}}
    original = manifest_audit(source, original_report, check_live_sources, source_root)
    preflight_audit(source, original, original_report)
    proof["source_checks"] = original_report["checks"]
    check(proof, "source_manifest_and_preflight", not original_report["errors"])
    check(
        proof,
        "source_manifest_identity",
        original["manifest_sha256"] == provenance["source_manifest_sha256"]
        and original_report["manifest_artifact_sha256"]
        == provenance["source_manifest_file_sha256"],
    )
    check(proof, "single_recovery_generation", "recovery" not in original)
    fields = (
        "format_version",
        "stage",
        "inputs",
        "jobs",
        "policy",
        "analysis_plan",
        "writer_model",
        "writer_variant",
        "judge_variant",
        "seed",
        "timeout",
        "max_attempts",
        "output_token_limit_requested",
        "opencode_version_required",
    )
    check(
        proof,
        "unchanged_frozen_study",
        all(same(frozen[k], original[k]) for k in fields),
    )
    check(
        proof,
        "fresh_judge_model",
        provenance["source_judge_model"] == original["judge_model"]
        and frozen["judge_model"]
        not in (original["judge_model"], original["writer_model"]),
    )
    check(
        proof,
        "recovery_script_metadata",
        provenance["script"] == "evals/documenting/rejudge.py"
        and isinstance(provenance["script_sha256"], str)
        and HASH.fullmatch(provenance["script_sha256"]),
    )
    if check_live_sources:
        check(
            proof,
            "recovery_script_hash",
            full.file_hash(within(source_root, provenance["script"]))
            == provenance["script_sha256"],
        )
    archived = provenance["writer_artifact_sha256"]
    source_hashes, copied_hashes = (
        writer_archive_hashes(source),
        writer_archive_hashes(output),
    )
    check(proof, "source_writer_archive", same(source_hashes, archived))
    check(proof, "copied_writer_archive", same(copied_hashes, archived))
    entries = {
        job["id"]: full.inspect_job(
            source, "writers", job, original["max_attempts"], verify=True
        )
        for job in original["jobs"]["writers"]
    }
    selections = {
        ident: entry["selected_first_valid"] for ident, entry in entries.items()
    }
    check(
        proof,
        "source_writer_selection",
        all(value is not None for value in selections.values())
        and all(
            a["status"] != "incomplete" for e in entries.values() for a in e["attempts"]
        )
        and same(provenance["selected_writer_attempts"], selections),
    )
    check(
        proof,
        "recovery_coverage",
        same(provenance["new_writer_calls"], 0)
        and same(provenance["reused_judge_attempts"], 0)
        and same(provenance["writer_jobs"], len(entries))
        and same(
            provenance["writer_attempts"],
            sum(len(e["attempts"]) for e in entries.values()),
        )
        and same(provenance["fresh_judge_jobs"], len(original["jobs"]["judges"]))
        and same(provenance["fresh_judge_splits"], list(full.SPLITS)),
    )
    proof.update(
        source_manifest_sha256=original["manifest_sha256"],
        source_manifest_file_sha256=original_report["manifest_artifact_sha256"],
        writer_files=len(archived),
        writer_jobs=len(entries),
        writer_attempts=sum(len(e["attempts"]) for e in entries.values()),
    )
    check(report, "recovery_provenance", not proof["errors"])
    if proof["errors"]:
        return None
    return {
        "output": source,
        "manifest": original,
        "archive": archived,
        "manifest_file_sha256": original_report["manifest_artifact_sha256"],
    }


def recovery_snapshot(output, context, report):
    check(
        report,
        "recovery_source_manifest_unchanged",
        full.file_hash(context["output"] / "manifest.json")
        == context["manifest_file_sha256"],
    )
    check(
        report,
        "recovery_source_archive_unchanged",
        same(writer_archive_hashes(context["output"]), context["archive"]),
    )
    check(
        report,
        "recovery_copy_archive_unchanged",
        same(writer_archive_hashes(output), context["archive"]),
    )


def inventory(output):
    """Include retries, unfinalized markers, out-of-bound attempts, and unknown jobs."""
    found, invalid = {}, 0
    for role in ROLES:
        parent = output / role
        if not parent.exists():
            continue
        for job in sorted(parent.iterdir()):
            if not job.is_dir() or job.is_symlink() or not NAME.fullmatch(job.name):
                invalid += 1
                continue
            for path in sorted(job.iterdir()):
                match = re.fullmatch(r"attempt-([1-9]\d*)(\.started\.json)?", path.name)
                if (
                    not match
                    or path.is_symlink()
                    or match[2]
                    and not path.is_file()
                    or not match[2]
                    and not path.is_dir()
                ):
                    invalid += 1
                    continue
                number = int(match[1])
                folder = job / ("attempt-" + str(number))
                found[role, job.name, number] = folder
    return found, invalid


def load_records(state, cutoff=None):
    for field, name, loader in (
        ("result", "result.json", read_object),
        ("native", "native-result.json", read_object),
        ("events", "events.jsonl", read_events),
        ("response", "response.json", read_object),
    ):
        path = state["folder"] / name
        if not path.exists():
            continue
        if cutoff is not None:
            # A live adapter may be writing this file. Only collect already
            # readable identities; ongoing attempts are never exported/validated.
            try:
                before = path.stat()
                value = loader(path)
                if before.st_mtime_ns <= cutoff and path.stat() == before:
                    state[field] = value
            except ERRORS:
                pass
        else:
            value = guarded(
                state["report"], field + "_read", lambda p=path, f=loader: f(p)
            )
            if value is not None:
                state[field] = value


def artifact_audit(state):
    trial, folder = state["report"], state["folder"]
    hashes = state["outcome"]["artifact_sha256"]
    actual = {
        p.name for p in folder.iterdir() if p.is_file() and p.name != "outcome.json"
    }
    check(trial, "artifact_inventory", set(hashes) == actual)
    for index, (name, expected) in enumerate(hashes.items()):
        # The runner records only basename artifacts. Invalid names must never
        # become paths or diagnostic strings containing arbitrary artifact text.
        if (
            re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name) is None
            or Path(name).name != name
            or name == "outcome.json"
        ):
            check(trial, "artifact_name_" + str(index), False)
            continue
        guarded(
            trial,
            "artifact_hash_" + name,
            lambda n=name, h=expected: check(
                trial, "artifact_hash_" + n, full.file_hash(within(folder, n)) == h
            ),
        )


def load_attempt(output, frozen, key, folder, cutoff, origin=None):
    role, ident, number = key
    trial = {
        "role": role,
        "job": ident,
        "attempt": number,
        "folder": str(folder.relative_to(output)),
        "errors": [],
        "checks": {},
        "response_status": "incomplete",
        "failure_kind": None,
        "session_ids": [],
        "session_verification": "unavailable",
    }
    state = {
        "key": key,
        "folder": folder,
        "report": trial,
        "ongoing": True,
        "outcome": {},
        "result": {},
        "native": {},
        "events": [],
        "response": {},
    }
    path = folder / "outcome.json"
    if not path.exists() or path.stat().st_mtime_ns > cutoff:
        load_records(state, cutoff)
        return state
    state["ongoing"] = False
    state["outcome_hash"] = full.file_hash(path)
    outcome = read_object(path)
    state["outcome"] = outcome
    status, kind = outcome.get("status"), outcome.get("failure_kind")
    check(
        trial,
        "outcome_metadata",
        status in ("valid", "failed")
        and kind in FAILURE_KINDS
        and (kind is None) == (status == "valid")
        and type(outcome.get("retryable")) is bool
        and outcome["retryable"]
        == (
            status != "valid"
            and kind in ("transport", "schema_or_evidence", "interrupted")
        ),
    )
    trial["response_status"] = (
        status if status in ("valid", "failed") else "unavailable"
    )
    trial["failure_kind"] = kind if kind in FAILURE_KINDS else "unavailable"

    guarded(trial, "artifacts", lambda: artifact_audit(state))

    def marker():
        origin_output, origin_manifest = (
            (origin["output"], origin["manifest"]) if origin else (output, frozen)
        )
        started = full.read_json(folder.with_name(folder.name + ".started.json"))
        check(
            trial,
            "started_marker",
            started["attempt"] == number
            and started["manifest_sha256"] == origin_manifest["manifest_sha256"],
        )
        invocation = full.read_json(
            within(origin_output, "invocations/" + started["invocation"] + ".json")
        )
        check(
            trial,
            "invocation",
            invocation["id"] == started["invocation"]
            and invocation["manifest_sha256"] == origin_manifest["manifest_sha256"]
            and invocation["arguments"]["command"] == role,
        )
        trial["origin_manifest_sha256"] = origin_manifest["manifest_sha256"]
        trial["reused_writer"] = origin is not None

    guarded(trial, "marker", marker)
    load_records(state)
    return state


def result_audit(state):
    trial, folder = state["report"], state["folder"]
    outcome, result, native = (state[k] for k in ("outcome", "result", "native"))
    recovered = (
        outcome.get("failure_kind") == "interrupted" and "full_validation" not in result
    )
    check(trial, "outcome_metrics", same(outcome["metrics"], full.metrics_only(result)))
    if not recovered:
        check(
            trial,
            "finalized_result",
            result["full_validation"] == outcome["status"]
            and result["status"]
            == ("completed" if outcome["status"] == "valid" else "failed")
            and result["failure_kind"] == outcome["failure_kind"]
            and same(result["failures"], outcome["failures"])
            and result["attempt_wall_seconds"] == outcome["wall_seconds"]
            and number(outcome["wall_seconds"]),
        )
        check(trial, "native_record_retained", bool(native) or "model" not in result)
    if native:
        check(
            trial,
            "native_result_fields",
            all(
                key in result and same(result[key], value)
                for key, value in native.items()
                if key not in ("status", "failures")
            ),
        )
        check(
            trial,
            "native_outcome_metrics",
            all(
                key in outcome["metrics"] and same(outcome["metrics"][key], value)
                for key, value in full.metrics_only(native).items()
            ),
        )
        if (
            outcome["status"] == "valid"
            or outcome["failure_kind"] == "schema_or_evidence"
        ):
            check(
                trial,
                "native_completion_record",
                native["status"] == "completed" and native["failures"] == [],
            )
    record = native or result
    if outcome.get("status") == "valid":
        required = {
            "result.json",
            "native-result.json",
            "system.md",
            "input.md",
            "config.json",
            "output.md",
            "events.jsonl",
        }
        required.update(
            {"checks.json"}
            if trial["role"] == "writers"
            else {
                "schema.json",
                "response.json",
                "structured.json",
                "mapping.json",
                "judgment.json",
            }
        )
        check(
            trial,
            "selected_artifact_coverage",
            required <= set(outcome["artifact_sha256"]),
        )
    if "model" not in record:
        return
    answer = text(folder / "output.md")
    check(trial, "output_word_count", record["output_words"] == len(answer.split()))
    check(trial, "duration", number(record["seconds"]))
    for name in ("system", "input", "output"):
        check(
            trial,
            name + "_sha256",
            full.file_hash(folder / (name + ".md")) == record[name + "_sha256"],
        )
    metrics = run.event_metrics(state["events"])
    if trial["role"] == "judges":
        metrics["provider_attempts"] = (
            "unavailable; OpenCode may retry internally; adapter does not retry"
        )
    check(
        trial,
        "native_event_metrics",
        all(same(record[k], v) for k, v in metrics.items()),
    )
    check(
        trial,
        "usage_numbers",
        all(number(n) for n in [*metrics["tokens"].values(), metrics["reported_cost"]]),
    )
    check(
        trial,
        "no_retained_reasoning_events",
        all(
            e.get("type") != "reasoning"
            and e.get("part", {}).get("type") != "reasoning"
            for e in state["events"]
        ),
    )
    if trial["role"] == "writers":
        check(
            trial,
            "event_output",
            "\n".join(
                e["part"]["text"] for e in state["events"] if e.get("type") == "text"
            )
            == answer,
        )
        if native.get("status") == "completed":
            check(
                trial,
                "writer_completion_protocol",
                record["exit_code"] == 0
                and record["timed_out"] is False
                and bool(answer.strip())
                and metrics["observed_model_steps"] == 1
                and all(r in ("stop", "end_turn") for r in metrics["finish_reasons"])
                and all(
                    e.get("type") in ("text", "step_start", "step_finish")
                    for e in state["events"]
                ),
            )


def collect_sessions(state):
    trial = state["report"]
    ids = set()
    lists = [
        record["session_ids"]
        for record in (
            state["native"],
            state["result"],
            state["outcome"].get("metrics", {}),
        )
        if isinstance(record, dict) and "session_ids" in record
    ]
    for values in lists:
        check(
            trial,
            "session_id_format",
            isinstance(values, list)
            and all(isinstance(v, str) and SESSION.fullmatch(v) for v in values),
        )
        if isinstance(values, list):
            ids.update(v for v in values if isinstance(v, str) and SESSION.fullmatch(v))
    events = state["events"]
    response = state["response"]
    parts = response.get("parts", [])
    check(trial, "response_parts_shape", isinstance(parts, list))
    envelopes = [
        *events,
        *(e.get("part", {}) for e in events),
        response.get("info", {}),
        *(parts if isinstance(parts, list) else []),
    ]
    for envelope in envelopes:
        if not isinstance(envelope, dict):
            check(trial, "transport_envelope_shape", False)
            continue
        if "sessionID" in envelope:
            value = envelope["sessionID"]
            valid = isinstance(value, str) and SESSION.fullmatch(value)
            check(trial, "transport_session_id_format", valid)
            if valid:
                ids.add(value)
    trial["session_ids"] = sorted(ids)
    if ids:
        check(
            trial,
            "one_transport_session",
            len(ids) == 1 and all(same(values, sorted(ids)) for values in lists),
        )
        check(
            trial, "event_session_ids", all(e.get("sessionID") in ids for e in events)
        )
    elif state["native"].get("status") == "completed":
        check(trial, "completed_session_present", False)
    return ids


def assignment_audit(state, frozen, selected, fixture_hashes):
    trial, folder, job = state["report"], state["folder"], state["job"]
    case = state["case"]
    writer = trial["role"] == "writers"
    model, variant = (
        frozen[k]
        for k in (
            ("writer_model", "writer_variant")
            if writer
            else ("judge_model", "judge_variant")
        )
    )
    system = (
        frozen["inputs"]["systems"][job["arm"]]
        if writer
        else frozen["inputs"]["judge_system"]
    )
    state["expected"] = system, None, model, variant
    if writer:
        prompt = run.writer_prompt(case)
    else:
        documents, mapping = (
            {},
            {
                key: job[key]
                for key in (
                    "case",
                    "repetition",
                    "pair",
                    "kind",
                    "primary_id",
                    "left",
                    "right",
                )
            },
        )
        mapping["writers"] = {}
        for side in ("left", "right"):
            source = selected[job[side + "_writer"]]
            path = source["folder"] / "output.md"
            digest = full.file_hash(path)
            check(
                trial,
                side + "_selected_writer_hash",
                digest == source["outcome"]["artifact_sha256"]["output.md"],
            )
            documents[side] = text(path)
            mapping["writers"][side] = {
                "job": job[side + "_writer"],
                "attempt": source["key"][2],
                "output_sha256": digest,
            }
        state["documents"] = documents
        prompt = full.json_text(
            full.judge_payload(case, documents["left"], documents["right"])
        )
        if (folder / "mapping.json").exists() or state["native"]:
            check(
                trial,
                "candidate_provenance",
                same(full.read_json(folder / "mapping.json"), mapping),
            )
    state["expected"] = system, prompt, model, variant
    record = state["native"] or state["result"]
    # An adapter can fail before creating input artifacts. Once present, even a
    # failed/invalid-schema attempt must have the exact assigned bytes/config.
    if (folder / "input.md").exists() or "model" in record:
        actual = text(folder / "input.md")
        check(trial, "assigned_input_without_labels", actual == prompt)
        check(trial, "assigned_system", text(folder / "system.md") == system)
        if writer:
            digest = run.digest(actual)
            check(
                trial,
                "identical_fixture_input_across_arms_repetitions",
                fixture_hashes.setdefault(case["id"], digest) == digest,
            )
        config = run.configuration(system, model)
        if not writer:
            permission = {"*": "deny", "StructuredOutput": "allow"}
            config["permission"] = permission
            config["agent"]["documentation-eval"]["permission"] = permission.copy()
            schema = frozen["inputs"]["judge_schemas"][case["id"]]
            check(
                trial,
                "assigned_schema",
                same(full.read_json(folder / "schema.json"), schema),
            )
            if "model" in record:
                check(
                    trial,
                    "schema_sha256",
                    full.file_hash(folder / "schema.json") == record["schema_sha256"],
                )
        check(
            trial,
            "isolated_configuration",
            same(full.read_json(folder / "config.json"), config),
        )
    if "model" in record:
        check(
            trial,
            "assigned_model_variant",
            record["model"] == model and record["variant"] == variant,
        )
    if writer and (folder / "checks.json").exists():
        checks = run.check_output(case, text(folder / "output.md"))
        check(
            trial,
            "writer_check_artifact",
            same(full.read_json(folder / "checks.json"), checks),
        )
        check(
            trial,
            "writer_check_metrics",
            state["result"]["check_count"] == len(checks)
            and state["result"]["failed_check_count"]
            == sum(not c["passed"] for c in checks),
        )


def judge_audit(state):
    trial, folder = state["report"], state["folder"]
    record = state["native"] or state["result"]
    ids = trial["session_ids"]
    if not ids:
        return
    trial["session_verification"] = "native_sse"
    _, _, model, variant = state["expected"]
    completed = record.get("status") == "completed"
    failures = record.get("failures", [])
    for name, field, failure, prerequisites in (
        (
            "native_user_input_audit",
            "actual_input_match",
            "Session input audit mismatch",
            record.get("transport") == "opencode-http"
            and record.get("input_audit_source") == "event_stream",
        ),
        (
            "native_fresh_session",
            "session_isolated",
            "Unexpected session history",
            type(record.get("prompt_posts")) is int
            and record["prompt_posts"] == 1
            and record.get("server_started") is True
            and record.get("server_ready") is True,
        ),
    ):
        flag = record.get(field)
        # The native adapter initializes these flags to false before starting.
        # Only a completed audit or its explicit mismatch diagnostic establishes
        # a negative finding; transport loss before that point is unknown.
        if (
            completed
            or flag is True
            or failure in failures
            or (field in record and type(flag) is not bool)
        ):
            check(trial, name, flag is True and prerequisites)
        else:
            unknown(trial, name)
    response = state["response"]
    info = response.get("info", {})
    if not info and not completed:
        unknown(trial, "actual_metadata_matches")
        return
    provider, model_id = model.split("/", 1)
    expected = {
        "role": "assistant",
        "sessionID": ids[0],
        "providerID": provider,
        "modelID": model_id,
        "variant": variant,
        "agent": "documentation-eval",
    }
    metadata_matches = (
        all(info.get(k) == v for k, v in expected.items())
        and structured._identifier(info.get("id"), "msg")
        and structured._identifier(info.get("parentID"), "msg")
    )
    if (
        metadata_matches
        or completed
        or any(k in info and info[k] != v for k, v in expected.items())
        or any("Assistant " + k + " mismatch" in failures for k in expected)
    ):
        check(trial, "actual_metadata_matches", metadata_matches)
    else:
        unknown(trial, "actual_metadata_matches")
    safe, events, value, failures = structured._parse_response(
        response, ids[0], model, variant
    )
    check(trial, "sanitized_native_response", same(safe, response))
    check(trial, "native_response_events", same(events, state["events"]))
    if record["status"] == "completed":
        check(
            trial,
            "native_completion_protocol",
            not failures and record["exit_code"] == 0 and record["timed_out"] is False,
        )
        check(
            trial,
            "native_structured_output",
            same(full.read_json(folder / "structured.json"), value)
            and text(folder / "output.md") == full.json_text(value),
        )
    if trial["response_status"] == "valid":
        judgment = full.read_json(folder / "judgment.json")
        check(trial, "selected_judgment_matches_native", same(judgment, value))
        try:
            judging.validate(
                judgment,
                state["case"],
                state["documents"]["left"],
                state["documents"]["right"],
            )
        except ERRORS:
            valid = False
        else:
            valid = True
        trial["selected_schema_quote_valid"] = valid
        check(trial, "selected_validity_record_matches", valid)


def finish_trial(state):
    trial = state["report"]
    required = ["one_transport_session", "globally_unique_transport_session"]
    required += (
        ["writer_session_export"]
        if trial["role"] == "writers"
        else [
            "native_user_input_audit",
            "native_fresh_session",
            "actual_metadata_matches",
        ]
    )
    checks = trial["checks"]
    if any(checks.get(name) is False for name in required):
        trial["session_integrity"] = "failed"
    elif (
        not state["ongoing"]
        and trial["session_ids"]
        and all(checks.get(name) is True for name in required)
    ):
        trial["session_integrity"] = "verified"
    else:
        trial["session_integrity"] = "unknown"
        unknown(trial, "session_evidence_unavailable")
    trial["integrity_status"] = (
        "failed"
        if trial["errors"]
        else "unknown"
        if trial.get("unknowns")
        else "passed"
    )


def audit(output, *, check_live_sources=False, workers=6, source_root=full.ROOT):
    """Return a metadata-only report. CLI publication is separate for offline use."""
    if type(workers) is not int or workers < 1:
        raise ValueError("workers must be positive")
    output = Path(output).resolve()
    cutoff = time.time_ns()
    report: dict = {
        "format_version": 2,
        "snapshot_utc": full.utc_now(),
        "errors": [],
        "checks": {},
        "attempts": [],
        "jobs": {role: {} for role in ROLES},
        "complete": False,
        "scope": "Integrity verdict excludes response quality; schema failures are counted separately.",
    }
    frozen = guarded(
        report,
        "manifest",
        lambda: manifest_audit(output, report, check_live_sources, Path(source_root)),
    )
    states, exports = [], []
    initial = None
    recovery = None
    if frozen is not None:
        report["manifest_sha256"] = frozen["manifest_sha256"]
        guarded(report, "preflight", lambda: preflight_audit(output, frozen, report))
        if "recovery" in frozen:
            recovery = guarded(
                report,
                "recovery",
                lambda: recovery_audit(
                    output, frozen, report, check_live_sources, Path(source_root)
                ),
            )

        def inspect():
            nonlocal initial
            planned = {
                (role, job["id"]): job for role in ROLES for job in frozen["jobs"][role]
            }
            report["planned_jobs"] = len(planned)
            cases = {case["id"]: case for case in frozen["inputs"]["cases"]}
            initial = inventory(output)
            check(report, "known_artifact_layout", initial[1] == 0)
            for key, folder in sorted(initial[0].items()):
                state = guarded(
                    report,
                    "attempt_read",
                    lambda k=key, f=folder: load_attempt(
                        output,
                        frozen,
                        k,
                        f,
                        cutoff,
                        recovery if k[0] == "writers" else None,
                    ),
                )
                if state is None:
                    trial = {
                        "role": key[0],
                        "job": key[1],
                        "attempt": key[2],
                        "folder": str(folder.relative_to(output)),
                        "errors": ["unreadable_attempt"],
                        "checks": {},
                        "response_status": "unavailable",
                        "failure_kind": "unavailable",
                        "session_ids": [],
                        "session_verification": "unavailable",
                    }
                    state = {
                        "key": key,
                        "folder": folder,
                        "report": trial,
                        "ongoing": False,
                        "outcome": {},
                        "result": {},
                        "native": {},
                        "events": [],
                        "response": {},
                    }
                    # Recover session accounting even when outcome.json is corrupt.
                    load_records(state)
                states.append(state)
                trial = state["report"]
                report["attempts"].append(trial)
                job = planned.get(key[:2])
                check(trial, "planned_assignment", job is not None)
                check(trial, "retry_bound", 1 <= key[2] <= frozen["max_attempts"])
                if job:
                    state.update(job=job, case=cases[job["case"]])
                guarded(
                    trial, "session_accounting", lambda s=state: collect_sessions(s)
                )
                if not state["ongoing"]:
                    guarded(trial, "result_integrity", lambda s=state: result_audit(s))
            grouped = defaultdict(list)
            for state in states:
                grouped[state["key"][:2]].append(state)
            selected = {}
            for (role, ident), job in planned.items():
                attempts = grouped[role, ident]
                numbers = [s["key"][2] for s in attempts]
                check(
                    report,
                    "consecutive_" + role + "/" + ident,
                    numbers == list(range(1, len(numbers) + 1)),
                )
                valid = next(
                    (s for s in attempts if s["report"]["response_status"] == "valid"),
                    None,
                )
                for earlier, later in zip(attempts, attempts[1:]):
                    check(
                        later["report"],
                        "retry_after_retryable_failure",
                        earlier["outcome"].get("status") == "failed"
                        and earlier["outcome"].get("retryable") is True,
                    )
                if role == "writers" and valid:
                    selected[ident] = valid
                ongoing = any(s["ongoing"] for s in attempts)
                terminal = (
                    not ongoing
                    and bool(
                        valid
                        or attempts
                        and (
                            len(attempts) >= frozen["max_attempts"]
                            or attempts[-1]["outcome"].get("retryable") is False
                        )
                    )
                    and all(
                        s["report"]["response_status"] in ("valid", "failed")
                        for s in attempts
                    )
                )
                status = (
                    "ongoing"
                    if ongoing
                    else "valid"
                    if valid
                    else "failed"
                    if terminal
                    else "retry_pending"
                    if attempts
                    else "pending"
                )
                report["jobs"][role][ident] = {
                    "status": status,
                    "terminal": terminal,
                    "attempts": len(attempts),
                    "selected_first_valid": valid["key"][2] if valid else None,
                    "split": job["split"],
                }
            for job in frozen["jobs"]["judges"]:
                entry = report["jobs"]["judges"][job["id"]]
                dependencies = [
                    report["jobs"]["writers"][job[side + "_writer"]]
                    for side in ("left", "right")
                ]
                if not entry["attempts"] and any(
                    d["terminal"] and d["selected_first_valid"] is None
                    for d in dependencies
                ):
                    entry.update(status="blocked", terminal=True)
            fixture_hashes = {}
            for state in states:
                if state["ongoing"] or "job" not in state:
                    continue
                trial = state["report"]
                guarded(
                    trial,
                    "assignment",
                    lambda s=state: assignment_audit(
                        s, frozen, selected, fixture_hashes
                    ),
                )
                if "expected" in state:
                    if trial["role"] == "judges":
                        guarded(trial, "native_judge", lambda s=state: judge_audit(s))
                    else:
                        exports.extend((state, sid) for sid in trial["session_ids"])
                if not trial["session_ids"]:
                    trial["session_verification"] = "no_observed_session"

        guarded(report, "inventory", inspect)

    seen = defaultdict(list)
    for state in states:
        for sid in state["report"]["session_ids"]:
            seen[sid].append(state["report"])
    for owners in seen.values():
        for trial in owners:
            check(trial, "globally_unique_transport_session", len(owners) == 1)

    def export(item):
        state, sid = item
        result = {"session_id": sid, "errors": [], "checks": {}}
        system, prompt, model, variant = state["expected"]
        try:
            session_audit(result, system, prompt, model, variant, sid)
        except ERRORS as error:
            unknown(result, "session_export_unavailable:" + type(error).__name__)
        return state, result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for state, result in pool.map(export, exports):
            trial = state["report"]
            trial.setdefault("exports", []).append(result)
            if result["errors"] or not result.get("unknowns"):
                check(trial, "writer_session_export", not result["errors"])
            else:
                unknown(trial, "writer_session_export")
            trial["session_verification"] = "cli_export"
    for state in states:
        trial = state["report"]
        if trial["session_ids"] and not state["ongoing"]:
            check(
                trial,
                "session_audit_accounted",
                trial["session_verification"] in ("cli_export", "native_sse"),
            )
        if "outcome_hash" in state:
            guarded(trial, "artifact_snapshot", lambda s=state: artifact_audit(s))
            guarded(
                trial,
                "outcome_snapshot",
                lambda s=state: check(
                    s["report"],
                    "outcome_unchanged",
                    full.file_hash(s["folder"] / "outcome.json") == s["outcome_hash"],
                ),
            )
        finish_trial(state)
    if recovery is not None:
        guarded(
            report,
            "recovery_snapshot",
            lambda: recovery_snapshot(output, recovery, report),
        )
    if "manifest_artifact_sha256" in report:
        guarded(
            report,
            "manifest_snapshot",
            lambda: check(
                report,
                "manifest_unchanged",
                full.file_hash(output / "manifest.json")
                == report["manifest_artifact_sha256"],
            ),
        )
    stable = (
        initial is not None
        and guarded(report, "final_inventory", lambda: inventory(output)) == initial
    )
    entries = [entry for jobs in report["jobs"].values() for entry in jobs.values()]
    report["complete"] = (
        bool(entries)
        and len(entries) == report.get("planned_jobs")
        and stable
        and all(e["terminal"] for e in entries)
        and all(
            not s["ongoing"] and s["report"]["checks"].get("planned_assignment")
            for s in states
        )
    )
    report["snapshot_stable"] = stable
    failures = sum(bool(s["report"]["errors"]) for s in states)
    unknown_attempts = sum(s["report"]["integrity_status"] == "unknown" for s in states)
    status = (
        "failed"
        if report["errors"] or failures
        else "unknown"
        if unknown_attempts
        else "passed"
    )
    report["integrity"] = {
        "status": status,
        "passed": False
        if status == "failed"
        else None
        if status == "unknown"
        else True,
        "known_checks_passed": not report["errors"] and failures == 0,
        "failed_attempts": failures,
        "unknown_attempts": unknown_attempts,
        "global_errors": len(report["errors"]),
    }
    report["passed"] = report["integrity"]["passed"]
    report["evaluation_response_validity"] = {
        **{
            role: dict(
                Counter(
                    s["report"]["response_status"]
                    for s in states
                    if s["key"][0] == role
                )
            )
            for role in ROLES
        },
        "schema_or_evidence_failures": sum(
            s["report"]["failure_kind"] == "schema_or_evidence" for s in states
        ),
        "selected_quote_validation_failures": sum(
            s["report"].get("selected_schema_quote_valid") is False for s in states
        ),
    }
    counts = Counter(e["status"] for e in entries)
    report["counts"] = {
        "planned": len(entries),
        "covered": sum(e["terminal"] for e in entries),
        **{
            k: counts[k]
            for k in (
                "valid",
                "failed",
                "blocked",
                "pending",
                "ongoing",
                "retry_pending",
            )
        },
        "attempts": len(states),
        "finalized_attempts": sum(not s["ongoing"] for s in states),
        "ongoing_attempts": sum(s["ongoing"] for s in states),
        "no_observed_session_attempts": sum(
            not s["report"]["session_ids"] for s in states
        ),
        "ongoing_sessions": sum(
            len(s["report"]["session_ids"]) for s in states if s["ongoing"]
        ),
        "unverified_transport_attempts": sum(
            bool(s["report"]["session_ids"])
            and s["report"]["session_integrity"] != "verified"
            for s in states
        ),
        "sessions": len(seen),
        "verified_session_attempts": sum(
            s["report"]["session_integrity"] == "verified" for s in states
        ),
        "unknown_session_attempts": sum(
            s["report"]["session_integrity"] == "unknown" for s in states
        ),
        "writer_exports": len(exports),
        "native_judge_sessions": sum(
            s["report"]["session_verification"] == "native_sse" for s in states
        ),
        "duplicate_sessions": sum(len(owners) > 1 for owners in seen.values()),
        "schema_or_evidence_failures": report["evaluation_response_validity"][
            "schema_or_evidence_failures"
        ],
        "integrity_failed_attempts": failures,
        "integrity_unknown_attempts": unknown_attempts,
        "integrity_passed_attempts": sum(
            s["report"]["integrity_status"] == "passed" for s in states
        ),
        "integrity_global_errors": len(report["errors"]),
        "complete": int(report["complete"]),
        "integrity_passed": int(report["passed"] is True),
        "known_checks_passed": int(report["integrity"]["known_checks_passed"]),
    }
    return report


def archive_previous_audit(output):
    path = output / "audit.json"
    if not path.exists():
        return None
    previous = read_object(path)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    archive = output / ("audit.previous-" + digest + ".json")
    if not archive.exists():
        with archive.open("xb") as stream:
            stream.write(raw)
    if full.file_hash(archive) != digest:
        raise ValueError("Previous audit archive changed")
    return {
        "artifact": archive.name,
        "sha256": digest,
        "interpretation": "Superseded diagnostic report, not evidence of trial integrity.",
        "global_error_counts": dict(Counter(previous.get("errors", []))),
        "attempt_error_counts": dict(
            Counter(
                error
                for trial in previous.get("attempts", [])
                for error in trial.get("errors", [])
            )
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check-live-sources", action="store_true")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be positive")
    previous = archive_previous_audit(args.output)
    report = audit(
        args.output, check_live_sources=args.check_live_sources, workers=args.workers
    )
    if previous is not None:
        report["previous_audit"] = previous
    full.save_cache(args.output / "audit.json", report)
    print(json.dumps(report["counts"], sort_keys=True))
    if report["passed"] is False:
        return 1
    if not report["complete"]:
        return 2
    return 3 if report["passed"] is None else 0


if __name__ == "__main__":
    sys.exit(main())
