#!/usr/bin/env python3
"""Frozen, resumable full-blind documentation evaluation (Python 3.9+).

Only writers/judges generate responses. validate, init (including metadata-only
preflight), status, and summarize do not run inference. --limit counts jobs,
including their bounded retries, rather than individual model calls.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import random
import re
import signal
import sys
import threading
import time
import types
import uuid


sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE_ROOT = HERE / "cases/full-blind"
CATEGORIES = (
    "clean-controls",
    "consistency",
    "duplication",
    "necessary-repetition",
    "organization",
    "technical-meaning",
)
SPLITS = ("development", "holdout")
ARMS = ("A", "B", "C")
PAIRS = (("A", "B"), ("B", "C"))
TOKENS = ("input", "output", "reasoning", "cache_read", "cache_write")
FORMAT_VERSION = 1


def import_source(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load evaluation source")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# A private package lets structured.py's relative import reuse this exact runner
# without changing sys.path or importing an unrelated module named 'run'.
PACKAGE = "_documenting_full_runtime"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(HERE)]
sys.modules[PACKAGE] = package
base = import_source(PACKAGE + ".run", HERE / "run.py")
structured = None
judging = None


def judge_module():
    global judging
    if judging is None:
        if not (HERE / "judging.py").is_file():
            raise ValueError("Full-suite judging.py is required for this command")
        judging = import_source(PACKAGE + ".judging", HERE / "judging.py")
    return judging


def structured_module():
    global structured
    if structured is None:
        structured = import_source(PACKAGE + ".structured", HERE / "structured.py")
    return structured


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def json_hash(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate JSON key")
            value[key] = item
        return value

    try:
        value = json.loads(Path(path).read_bytes(), object_pairs_hook=unique)
        json_hash(value)  # Also reject NaN/Infinity, including overflowing floats.
        return value
    except (ValueError, UnicodeError, RecursionError):
        # Decoder errors can contain source text. Diagnostics must be metadata-only.
        raise ValueError("Invalid JSON artifact") from None


def save_new(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(json_text(value))
            stream.flush()
            os.fsync(stream.fileno())
        # link() fails on an existing destination and publishes a whole record.
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def save_cache(path, value):
    """Only derived caches/finalized metadata are replaceable, atomically."""
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    save_new(temporary, value)
    os.replace(temporary, path)


class OutputBusy(ValueError):
    pass


@contextmanager
def output_lock(output):
    with (output / ".execution.lock").open("a") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise OutputBusy("Another command is using this output directory") from None
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate_case(case):
    if not isinstance(case, dict):
        raise ValueError("Case must be an object")
    for field in ("id", "family", "task", "source_facts", "draft", "split"):
        if not nonempty(case.get(field)):
            raise ValueError("Missing or invalid case field: " + field)
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", case["id"]) is None:
        raise ValueError("Unsafe case ID")
    if case["split"] not in SPLITS:
        raise ValueError("Invalid case split")
    for field in ("requirements", "issues", "checks"):
        items = case.get(field)
        if not isinstance(items, list) or (field == "requirements" and not items):
            raise ValueError("Invalid annotation array: " + field)
        if any(
            not isinstance(item, dict) or not nonempty(item.get("id")) for item in items
        ):
            raise ValueError("Invalid annotation ID: " + field)
        ids = [item["id"] for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate annotation IDs: " + field)
        for item in items:
            if "text" in item and not nonempty(item["text"]):
                raise ValueError("Invalid annotation text")
    requirements = {item["id"] for item in case["requirements"]}
    for check in case["checks"]:
        if check.get("requirement") not in requirements:
            raise ValueError("Check references unknown requirement")
        if check.get("kind") not in (
            "contains",
            "not_contains",
            "count_at_least",
            "regex",
        ):
            raise ValueError("Unknown preservation check")
        if not nonempty(check.get("value")):
            raise ValueError("Invalid preservation check value")
        if check["kind"] == "count_at_least" and (
            type(check.get("minimum")) is not int or check["minimum"] < 1
        ):
            raise ValueError("Invalid preservation count")
    try:
        checks = base.check_output(case, case["draft"])
    except (ValueError, TypeError, KeyError, re.error):
        raise ValueError("Invalid preservation checks") from None
    if not all(check["passed"] for check in checks):
        raise ValueError("Original draft fails a preservation proxy")


def validate_suite(cases, metadata):
    """The public suite boundary is strict; scheduling helpers accept small fixtures."""
    if len(cases) != 36 or len({case["id"] for case in cases}) != 36:
        raise ValueError("Full suite requires exactly 36 distinct cases")
    if set(metadata) != {case["id"] for case in cases}:
        raise ValueError("Case metadata coverage mismatch")
    counts = Counter()
    for case in cases:
        validate_case(case)
        meta = metadata[case["id"]]
        if meta["category"] not in CATEGORIES or meta["split"] != case["split"]:
            raise ValueError("Case routing mismatch")
        counts[meta["category"], meta["split"]] += 1
    expected = Counter(
        {
            (category, split): count
            for category in CATEGORIES
            for split, count in (("development", 2), ("holdout", 4))
        }
    )
    if counts != expected:
        raise ValueError(
            "Each of six categories requires 2 development and 4 holdout cases"
        )


def load_cases():
    paths = sorted(CASE_ROOT.glob("*/*.json"))
    if len(paths) != 36:
        raise ValueError("Full suite requires exactly 36 source files")
    cases, metadata = [], {}
    for path in paths:
        case = read_json(path)
        validate_case(case)
        category = path.parent.name
        if "category" in case and case["category"] != category:
            raise ValueError("Case category does not match its source directory")
        cases.append(case)
        metadata[case["id"]] = {
            "category": category,
            "split": case["split"],
            "source": str(path.relative_to(ROOT)),
            "source_sha256": file_hash(path),
            "embedded_sha256": json_hash(case),
        }
    validate_suite(cases, metadata)
    return cases, metadata


def load_inputs():
    cases, metadata = load_cases()
    original = base.load_inputs()
    module = judge_module()
    system = module.system_prompt()
    if not nonempty(system):
        raise ValueError("Missing full-suite judge system prompt")
    schemas = {case["id"]: module.schema_for(case) for case in cases}
    if any(
        not isinstance(schema, dict) or schema.get("type") != "object"
        for schema in schemas.values()
    ):
        raise ValueError("Judge schemas must describe JSON objects")
    sources = {ROOT / name for name in original["source_hashes"]}
    sources.update(HERE / name for name in ("full.py", "structured.py", "judging.py"))
    return {
        "cases": cases,
        "case_metadata": metadata,
        "systems": original["systems"],
        "judge_system": system,
        "judge_schemas": schemas,
        "source_hashes": {
            str(path.relative_to(ROOT)): file_hash(path) for path in sorted(sources)
        },
    }


def writer_id(case_id, repetition, arm):
    return case_id + "-r" + str(repetition) + "-" + arm


def make_schedule(cases, metadata, seed):
    writers, primaries = [], []
    order_rng = random.Random(seed + 1)
    for case in sorted(cases, key=lambda item: item["id"]):
        routing = {key: metadata[case["id"]][key] for key in ("split", "category")}
        for repetition in range(1, 4):
            common = {"case": case["id"], "repetition": repetition, **routing}
            for arm in ARMS:
                writers.append(
                    {**common, "id": writer_id(case["id"], repetition, arm), "arm": arm}
                )
            for pair in PAIRS:
                left, right = pair if order_rng.randrange(2) == 0 else pair[::-1]
                name = writer_id(case["id"], repetition, "".join(pair))
                primaries.append(
                    {
                        **common,
                        "id": name + "-primary",
                        "pair": "".join(pair),
                        "kind": "primary",
                        "primary_id": name + "-primary",
                        "left": left,
                        "right": right,
                        "left_writer": writer_id(case["id"], repetition, left),
                        "right_writer": writer_id(case["id"], repetition, right),
                    }
                )
    # Exactly 25% within category x split: 3/12 development and 6/24
    # holdout primaries. The sampled unit is the comparison, never its answer.
    strata = defaultdict(list)
    for job in primaries:
        strata[job["category"], job["split"]].append(job)
    sample_rng = random.Random(seed + 2)
    swaps = []
    for key in sorted(strata):
        group = strata[key]
        for job in sample_rng.sample(group, len(group) // 4):
            swaps.append(
                {
                    **job,
                    "id": job["id"][: -len("-primary")] + "-swap",
                    "kind": "swap",
                    "left": job["right"],
                    "right": job["left"],
                    "left_writer": job["right_writer"],
                    "right_writer": job["left_writer"],
                }
            )
    random.Random(seed).shuffle(writers)
    judges = primaries + swaps
    random.Random(seed + 3).shuffle(judges)
    return {"writers": writers, "judges": judges}


def sanitized_arguments(command, **options):
    # Never persist argv verbatim, environment variables, or credentials.
    allowed = (
        "output",
        "split",
        "limit",
        "concurrency",
        "seed",
        "timeout",
        "max_attempts",
    )
    return {
        "command": command,
        **{
            key: str(value) if isinstance(value, Path) else value
            for key, value in options.items()
            if key in allowed
        },
    }


def make_manifest(inputs, seed=base.SEED, timeout=600, max_attempts=2, arguments=None):
    if type(max_attempts) is not int or max_attempts not in (1, 2):
        raise ValueError("max_attempts must be 1 or 2")
    if type(timeout) is not int or timeout < 1 or type(seed) is not int:
        raise ValueError("Invalid frozen timeout or seed")
    value = {
        "format_version": FORMAT_VERSION,
        "stage": "full-blind",
        "created_utc": utc_now(),
        "seed": seed,
        "max_attempts": max_attempts,
        "writer_model": base.WRITER_MODEL,
        "writer_variant": "high",
        "judge_model": base.JUDGE_MODEL,
        "judge_variant": "high",
        "timeout": timeout,
        "output_token_limit_requested": base.TOKEN_LIMIT,
        "opencode_version_required": base.VERSION,
        "versions": {
            "python": platform.python_version(),
            "driver_format": FORMAT_VERSION,
            "opencode_required": base.VERSION,
        },
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "arguments": arguments
        or sanitized_arguments(
            "init", seed=seed, timeout=timeout, max_attempts=max_attempts
        ),
        "inputs": inputs,
        "jobs": make_schedule(inputs["cases"], inputs["case_metadata"], seed),
        "policy": {
            "selection": "first valid attempt; never retry semantic failures or uncertainty",
            "phase_order": "all development jobs terminal before holdout",
            "swap_sampling": "25% of primaries within each category and split",
            "permissions": {
                "writer": {"*": "deny"},
                "judge": {"*": "deny", "StructuredOutput": "allow"},
            },
            "provider_attempts": "unavailable; adapters may have internal provider retries",
        },
        "analysis_plan": {
            "primary_comparison": "C versus B on held-out cases; A versus B is secondary",
            "primary_score": "C win +1, B win -1, tie/uncertain 0; average valid primary repetitions within each document, then average documents equally",
            "uncertainty": "95% percentile bootstrap of documents within category, 10000 resamples, seed 46075; repetitions and swapped judgments are not independent documents",
            "secondary_measures": "Paired atomic requirement failure fraction, known-issue resolution (resolved=1, partial=0.5, unresolved/uncertain=0), organization, unnecessary change, critical regression flags, length and operational reliability",
            "adoption": "Adopt C only if the primary interval lower bound exceeds zero, its paired requirement-failure fraction does not increase, and no new critical regression is confirmed; otherwise retain B",
            "coverage_gate": "At least 90% of planned primary BC judgments valid, with at least two valid primary repetitions for every held-out document; failures and uncertainty also reported explicitly",
            "order_swaps": "Reliability diagnostic only; exclude swaps from primary effect and report incomplete pairs separately",
            "adjudication": "Review critical flags and substantive disputed findings against sources; retain original assessments and label secondary AI-assisted review",
            "scope": "Synthetic fixed-draft finalization with frozen prompts; not initial drafting, normal agent tools, automatic skill loading, or evidence of universal model behavior",
        },
    }
    value["manifest_sha256"] = json_hash(value)
    return value


def load_frozen(output):
    frozen = read_json(output / "manifest.json")
    signature = frozen.get("manifest_sha256")
    if signature != json_hash(
        {k: v for k, v in frozen.items() if k != "manifest_sha256"}
    ):
        raise ValueError("Manifest hash mismatch")
    if (
        frozen.get("format_version") != FORMAT_VERSION
        or frozen.get("stage") != "full-blind"
    ):
        raise ValueError("Unsupported manifest")
    # Explicit runtime sources and embedded cases only. Reports/analysis docs are
    # deliberately outside the freeze; no repository-wide or calibration hash.
    if frozen["inputs"] != load_inputs():
        raise ValueError(
            "Frozen sources, prompts, schemas, or cases changed; use a new output"
        )
    if frozen["jobs"] != make_schedule(
        frozen["inputs"]["cases"], frozen["inputs"]["case_metadata"], frozen["seed"]
    ):
        raise ValueError("Frozen schedule mismatch")
    return frozen


def verify_preflight(checks, frozen):
    if checks.get("version") != frozen["opencode_version_required"]:
        raise ValueError("Preflight CLI version mismatch")
    for field in (
        "prompt_matches",
        "all_resolved_tools_disabled",
        "no_configured_instructions_plugins_mcp",
    ):
        if checks.get(field) is not True:
            raise ValueError("Incomplete isolation preflight")
    for role in ("writer", "judge"):
        metadata = checks.get("models", {}).get(role, {})
        provider, model_id = frozen[role + "_model"].split("/", 1)
        if metadata.get("id") != model_id or metadata.get("providerID") != provider:
            raise ValueError("Preflight model metadata mismatch: " + role)
        variants = metadata.get("variants")
        if not isinstance(variants, dict) or frozen[role + "_variant"] not in variants:
            raise ValueError("Requested high variant unavailable: " + role)


def initialize(output, seed=base.SEED, timeout=600, max_attempts=2):
    output.mkdir(parents=True, exist_ok=True)
    with output_lock(output):
        if (output / "manifest.json").exists():
            frozen = load_frozen(output)
            if (seed, timeout, max_attempts) != (
                frozen["seed"],
                frozen["timeout"],
                frozen["max_attempts"],
            ):
                raise ValueError(
                    "Initialization options differ from the frozen manifest"
                )
        else:
            if any(path.name != ".execution.lock" for path in output.iterdir()):
                raise ValueError("A new evaluation requires an empty output directory")
            frozen = make_manifest(
                load_inputs(),
                seed,
                timeout,
                max_attempts,
                sanitized_arguments(
                    "init",
                    output=output,
                    seed=seed,
                    timeout=timeout,
                    max_attempts=max_attempts,
                ),
            )
            save_new(output / "manifest.json", frozen)
        if not (output / "ready.json").exists():
            # Every preflight gets a fresh directory, including failed/resumed init.
            folder = output / "preflights" / uuid.uuid4().hex
            folder.mkdir(parents=True)
            base.preflight(folder, frozen)
            checks = read_json(folder / "preflight.json")
            verify_preflight(checks, frozen)  # base checks only the writer variant.
            save_new(
                output / "ready.json",
                {
                    "manifest_sha256": frozen["manifest_sha256"],
                    "preflight": str(folder.relative_to(output) / "preflight.json"),
                    "preflight_sha256": file_hash(folder / "preflight.json"),
                    "writer_variant": "high",
                    "judge_variant": "high",
                },
            )
        require_ready(output, frozen)
        save_cache(output / "jobindex.json", build_index(output, frozen))
        return frozen


def require_ready(output, frozen):
    if not (output / "ready.json").exists():
        raise ValueError("Run init to complete metadata preflight first")
    ready = read_json(output / "ready.json")
    path = output / ready["preflight"]
    if (
        ready["manifest_sha256"] != frozen["manifest_sha256"]
        or file_hash(path) != ready["preflight_sha256"]
    ):
        raise ValueError("Preflight freeze mismatch")
    verify_preflight(read_json(path), frozen)


def inspect_job(output, role, job, maximum, verify=False):
    folder = output / role / job["id"]
    for path in folder.glob("attempt-*"):
        match = re.fullmatch(r"attempt-(\d+)(?:\.started\.json)?", path.name)
        if match and not 1 <= int(match[1]) <= maximum:
            raise ValueError("Attempt exceeds frozen retry bound")
    attempts = []
    for number in range(1, maximum + 1):
        attempt = folder / ("attempt-" + str(number))
        marker = folder / (attempt.name + ".started.json")
        if not attempt.exists() and not marker.exists():
            continue
        if (attempt / "outcome.json").exists():
            outcome = read_json(attempt / "outcome.json")
            if verify:
                for name, expected in outcome["artifact_sha256"].items():
                    if Path(name).name != name or file_hash(attempt / name) != expected:
                        raise ValueError("Retained attempt artifact changed")
        else:
            outcome = {
                "status": "incomplete",
                "failure_kind": "interrupted",
                "failures": ["Attempt has no finalized outcome"],
                "metrics": {},
            }
        attempts.append(
            {**outcome, "attempt": number, "folder": str(attempt.relative_to(output))}
        )
    if [item["attempt"] for item in attempts] != list(range(1, len(attempts) + 1)):
        raise ValueError("Nonconsecutive attempt artifacts")
    selected = next(
        (item["attempt"] for item in attempts if item["status"] == "valid"), None
    )
    return {
        "split": job["split"],
        "category": job["category"],
        "attempts": attempts,
        "selected_first_valid": selected,
        "first_attempt_status": attempts[0]["status"] if attempts else None,
        "status": "valid"
        if selected
        else (attempts[-1]["status"] if attempts else "pending"),
        "terminal": (
            selected is not None
            or len(attempts) >= maximum
            or bool(attempts and attempts[-1].get("retryable") is False)
        ),
    }


def refresh_dependencies(index, frozen):
    for job in frozen["jobs"]["judges"]:
        entry = index["jobs"]["judges"][job["id"]]
        if entry["selected_first_valid"] is not None:
            continue
        dependencies = [
            index["jobs"]["writers"][job[side + "_writer"]]
            for side in ("left", "right")
        ]
        entry["ready"] = all(
            item["selected_first_valid"] is not None for item in dependencies
        )
        if any(
            item["terminal"] and item["selected_first_valid"] is None
            for item in dependencies
        ):
            entry.update(status="blocked", terminal=True)


def build_index(output, frozen, verify=False):
    index = {
        "manifest_sha256": frozen["manifest_sha256"],
        "updated_utc": utc_now(),
        "jobs": {},
    }
    for role, jobs in frozen["jobs"].items():
        index["jobs"][role] = {
            job["id"]: inspect_job(output, role, job, frozen["max_attempts"], verify)
            for job in jobs
        }
    refresh_dependencies(index, frozen)
    return index


def development_complete(index):
    return all(
        entry["terminal"]
        for jobs in index["jobs"].values()
        for entry in jobs.values()
        if entry["split"] == "development"
    )


def judge_payload(case, left_text, right_text):
    return {
        **{
            key: case[key]
            for key in ("task", "source_facts", "draft", "requirements", "issues")
        },
        "candidates": {"left": left_text, "right": right_text},
    }


def candidate_inputs(output, job, index):
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
        ident = job[side + "_writer"]
        entry = index["jobs"]["writers"][ident]
        selected = entry["selected_first_valid"]
        if selected is None:
            raise ValueError("Judge dependency has no valid writer")
        attempt = next(
            item for item in entry["attempts"] if item["attempt"] == selected
        )
        path = output / attempt["folder"] / "output.md"
        if file_hash(path) != attempt["artifact_sha256"]["output.md"]:
            raise ValueError("Selected writer output changed")
        documents[side] = path.read_bytes().decode("utf-8")
        mapping["writers"][side] = {
            "job": ident,
            "attempt": selected,
            "output_sha256": file_hash(path),
        }
    return documents, mapping


def metrics_only(result):
    fields = (
        "seconds",
        "observed_model_steps",
        "reported_cost",
        "tokens",
        "output_words",
        "check_count",
        "failed_check_count",
        "server_start_seconds",
        "prompt_posts",
        "provider_attempts",
        "session_ids",
    )
    return {key: result[key] for key in fields if key in result}


def finalize_attempt(folder, result, status, failure_kind, failures, elapsed):
    folder.mkdir(parents=True, exist_ok=True)
    native = folder / "result.json"
    if native.exists() and not (folder / "native-result.json").exists():
        with (folder / "native-result.json").open("xb") as stream:
            stream.write(native.read_bytes())
    result = dict(result)
    result.update(
        status="completed" if status == "valid" else "failed",
        failures=failures,
        full_validation=status,
        failure_kind=failure_kind,
        attempt_wall_seconds=elapsed,
    )
    save_cache(native, result)
    artifacts = {
        path.name: file_hash(path) for path in folder.iterdir() if path.is_file()
    }
    outcome = {
        "status": status,
        "failure_kind": failure_kind,
        "retryable": status != "valid"
        and failure_kind in ("transport", "schema_or_evidence", "interrupted"),
        "failures": failures,
        "metrics": metrics_only(result),
        "wall_seconds": elapsed,
        "artifact_sha256": artifacts,
    }
    save_new(folder / "outcome.json", outcome)
    return outcome


def recover_incomplete(output, index):
    # Called only while holding the OS lock, so these cannot be live attempts.
    # Existing native artifacts are never rewritten during crash recovery.
    for jobs in index["jobs"].values():
        for entry in jobs.values():
            for attempt in entry["attempts"]:
                if attempt["status"] != "incomplete":
                    continue
                folder = output / attempt["folder"]
                folder.mkdir(parents=True, exist_ok=True)
                try:
                    result = (
                        read_json(folder / "result.json")
                        if (folder / "result.json").exists()
                        else {}
                    )
                except ValueError:
                    result = {}  # A killed adapter may leave a partial result file.
                save_new(
                    folder / "outcome.json",
                    {
                        "status": "failed",
                        "failure_kind": "interrupted",
                        "retryable": True,
                        "failures": [
                            "Interrupted attempt retained without a finalized validation"
                        ],
                        "metrics": metrics_only(result),
                        "wall_seconds": None,
                        "artifact_sha256": {
                            path.name: file_hash(path)
                            for path in folder.iterdir()
                            if path.is_file()
                        },
                    },
                )


def run_attempt(output, frozen, role, job, case, number, index, invocation):
    parent = output / role / job["id"]
    parent.mkdir(parents=True, exist_ok=True)
    folder = parent / ("attempt-" + str(number))
    save_new(
        parent / (folder.name + ".started.json"),
        {
            "invocation": invocation,
            "started_utc": utc_now(),
            "attempt": number,
            "manifest_sha256": frozen["manifest_sha256"],
        },
    )
    result, status, failure_kind, failures = {}, "failed", "transport", []
    stage = "setup"
    start = time.monotonic()
    try:
        if role == "writers":
            stage = "transport"
            result, text = base.call_model(
                folder,
                frozen["inputs"]["systems"][job["arm"]],
                base.writer_prompt(case),
                frozen["writer_model"],
                frozen["writer_variant"],
                frozen["timeout"],
            )
            stage = "artifacts"
            checks = base.check_output(case, text)
            save_new(folder / "checks.json", checks)
            result = {
                **result,
                "check_count": len(checks),
                "failed_check_count": sum(not check["passed"] for check in checks),
            }
            # Preservation failures measure quality; they are NOT retry reasons.
            if result["status"] == "completed":
                status, failure_kind = "valid", None
        else:
            documents, mapping = candidate_inputs(output, job, index)
            stage = "transport"
            result, value = structured_module().call_structured(
                folder,
                frozen["inputs"]["judge_system"],
                json_text(judge_payload(case, documents["left"], documents["right"])),
                frozen["inputs"]["judge_schemas"][case["id"]],
                model=frozen["judge_model"],
                variant=frozen["judge_variant"],
                timeout=frozen["timeout"],
            )
            stage = "artifacts"
            save_new(folder / "mapping.json", mapping)
            if result["status"] == "completed":
                failure_kind = "schema_or_evidence"
                try:
                    judge_module().validate(
                        value, case, documents["left"], documents["right"]
                    )
                except (ValueError, TypeError, KeyError):
                    failures.append("Judge schema or quote evidence validation failed")
                else:
                    save_new(folder / "judgment.json", value)
                    status, failure_kind = "valid", None
        failures = list(result.get("failures", [])) + failures
    except (KeyboardInterrupt, SystemExit):
        status = "failed"
        failure_kind = "interrupted"
        failures.append("Attempt interrupted")
    except OSError as error:
        status = "failed"
        failure_kind = "transport" if stage == "transport" else "local_failure"
        failures.append("Adapter " + stage + " failure: " + type(error).__name__)
    except Exception as error:
        # Exception bodies may include candidate text or provider secrets.
        failures.append("Local adapter/validation failure: " + type(error).__name__)
        status = "failed"
        failure_kind = "local_failure"
    if not result and (folder / "result.json").exists():
        result = read_json(folder / "result.json")
    return finalize_attempt(
        folder, result, status, failure_kind, failures, time.monotonic() - start
    )


def invocation_start(output, arguments, frozen):
    folder = output / "invocations"
    folder.mkdir(exist_ok=True)
    ident = uuid.uuid4().hex
    save_new(
        folder / (ident + ".json"),
        {
            "id": ident,
            "started_utc": utc_now(),
            "arguments": arguments,
            "manifest_sha256": frozen["manifest_sha256"],
            "pid": os.getpid(),
            "versions": {"python": platform.python_version(), "opencode": base.VERSION},
        },
    )
    return ident


def run_jobs(output, frozen, role, split="development", limit=None, concurrency=3):
    if role not in ("writers", "judges") or split not in (*SPLITS, "all"):
        raise ValueError("Invalid role or split")
    if concurrency < 1 or (limit is not None and limit < 1):
        raise ValueError("concurrency and limit must be positive")
    with output_lock(output):
        require_ready(output, frozen)
        index = build_index(output, frozen, verify=True)
        recover_incomplete(output, index)
        index = build_index(output, frozen, verify=True)
        if split == "holdout" and not development_complete(index):
            raise ValueError(
                "Development writers and judges must finish before holdout"
            )
        invocation = invocation_start(
            output,
            sanitized_arguments(
                role, output=output, split=split, limit=limit, concurrency=concurrency
            ),
            frozen,
        )
        start = time.monotonic()
        stop = threading.Event()
        mutex = threading.Lock()
        completed, launched = [], []
        cases = {case["id"]: case for case in frozen["inputs"]["cases"]}

        def cache():
            refresh_dependencies(index, frozen)
            index["updated_utc"] = utc_now()
            save_cache(output / "jobindex.json", index)

        def work(job):
            entry = index["jobs"][role][job["id"]]
            while not entry["terminal"] and not stop.is_set():
                number = len(entry["attempts"]) + 1
                outcome = run_attempt(
                    output,
                    frozen,
                    role,
                    job,
                    cases[job["case"]],
                    number,
                    index,
                    invocation,
                )
                with mutex:
                    entry = inspect_job(output, role, job, frozen["max_attempts"])
                    index["jobs"][role][job["id"]] = entry
                    cache()
                print(
                    role,
                    job["split"],
                    job["id"],
                    "attempt",
                    number,
                    outcome["status"],
                    flush=True,
                )
                if outcome["failure_kind"] in ("local_failure", "interrupted"):
                    # Programming errors/interrupts should not trigger automatic
                    # additional paid calls in the same invocation.
                    if outcome["failure_kind"] == "interrupted":
                        stop.set()
                    break
            return job["id"]

        interrupted = False
        error_type = None
        try:
            cache()
            for phase in SPLITS if split == "all" else (split,):
                if stop.is_set():
                    interrupted = True
                    break
                if phase == "holdout" and not development_complete(index):
                    break
                remaining = None if limit is None else limit - len(launched)
                if remaining == 0:
                    break
                jobs = [
                    job
                    for job in frozen["jobs"][role]
                    if job["split"] == phase
                    and not index["jobs"][role][job["id"]]["terminal"]
                    and (
                        role == "writers" or index["jobs"][role][job["id"]].get("ready")
                    )
                ]
                if remaining is not None:
                    jobs = jobs[:remaining]
                # Submit at most concurrency jobs. An interrupt cannot leave a
                # large queue that continues making calls after the user stops us.
                with ThreadPoolExecutor(max_workers=concurrency) as pool:
                    iterator = iter(jobs)
                    pending = {}

                    def submit_next():
                        if stop.is_set():
                            return
                        job = next(iterator, None)
                        if job is not None:
                            launched.append(job["id"])
                            pending[pool.submit(work, job)] = job["id"]

                    try:
                        for _ in range(min(concurrency, len(jobs))):
                            submit_next()
                        while pending:
                            done, _ = wait(pending, return_when=FIRST_COMPLETED)
                            for future in done:
                                completed.append(future.result())
                                del pending[future]
                                print(
                                    "Progress",
                                    len(completed),
                                    "/",
                                    len(launched),
                                    "jobs",
                                    flush=True,
                                )
                                submit_next()
                    except BaseException:
                        stop.set()
                        raise
            interrupted = stop.is_set()
        except (KeyboardInterrupt, SystemExit):
            interrupted = True
        except Exception as error:
            error_type = type(error).__name__
            raise
        finally:
            index = build_index(output, frozen)
            save_cache(output / "jobindex.json", index)
            save_new(
                output / "invocations" / (invocation + ".finished.json"),
                {
                    "id": invocation,
                    "finished_utc": utc_now(),
                    "wall_seconds": time.monotonic() - start,
                    "interrupted": interrupted,
                    "error_type": error_type,
                    "launched_jobs": launched,
                    "completed_jobs": completed,
                    "concurrency": concurrency,
                },
            )
        if interrupted:
            raise KeyboardInterrupt
        return status_counts(index)


def status_counts(index):
    counts = {}
    for split in (*SPLITS, "all"):
        counts[split] = {}
        for role, jobs in index["jobs"].items():
            entries = [
                entry
                for entry in jobs.values()
                if split == "all" or entry["split"] == split
            ]
            counts[split][role] = {
                "planned": len(entries),
                "attempted": sum(bool(item["attempts"]) for item in entries),
                "valid": sum(
                    item["selected_first_valid"] is not None for item in entries
                ),
                "failed": sum(
                    bool(item["attempts"])
                    and item["selected_first_valid"] is None
                    and item["status"] != "incomplete"
                    for item in entries
                ),
                "blocked": sum(item["status"] == "blocked" for item in entries),
                "incomplete": sum(item["status"] == "incomplete" for item in entries),
                "terminal": sum(item["terminal"] for item in entries),
                "attempts": sum(len(item["attempts"]) for item in entries),
                "first_attempt_valid": sum(
                    item["first_attempt_status"] == "valid" for item in entries
                ),
                "first_attempt_failed": sum(
                    item["first_attempt_status"] == "failed" for item in entries
                ),
                "retry_selected": sum(
                    (item["selected_first_valid"] or 0) > 1 for item in entries
                ),
            }
    return counts


def status(output, frozen):
    def snapshot():
        index = build_index(output, frozen)
        report = {
            "stage": frozen["stage"],
            "manifest_sha256": frozen["manifest_sha256"],
            "counts": status_counts(index),
            "development_complete": development_complete(index),
            "ready": (output / "ready.json").exists(),
            "index": "jobindex.json",
        }
        return index, report

    try:
        with output_lock(output):
            index, report = snapshot()
            save_cache(output / "jobindex.json", index)
            save_cache(output / "status.json", report)
    except OutputBusy:
        _, report = snapshot()
        report["execution_active"] = True
    return report


def usage(attempts):
    def number(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0

    def observed(item):
        steps = item["metrics"].get("observed_model_steps")
        return number(steps) and steps > 0

    def total(field):
        values = [
            item["metrics"].get(field)
            if field != "reported_cost" or observed(item)
            else None
            for item in attempts
        ]
        known = [
            value
            for value in values
            if isinstance(value, (int, float)) and number(value)
        ]
        return {
            "sum": sum(known),
            "known_attempts": len(known),
            "unknown_attempts": len(values) - len(known),
        }

    token_totals = {}
    for key in TOKENS:
        # Both frozen adapters use zero-filled totals when no usage event exists.
        # Preserve those native records, but do not count the placeholders as
        # observed zero usage in summaries of failed/interrupted transports.
        values = [
            item["metrics"].get("tokens", {}).get(key) if observed(item) else None
            for item in attempts
        ]
        known = [
            value
            for value in values
            if isinstance(value, (int, float)) and number(value)
        ]
        token_totals[key] = {
            "sum": sum(known),
            "known_attempts": len(known),
            "unknown_attempts": len(values) - len(known),
        }
    return {
        "attempts": len(attempts),
        "usage_observed_attempts": sum(observed(item) for item in attempts),
        "valid": sum(item["status"] == "valid" for item in attempts),
        "tokens": token_totals,
        **{
            field: total(field)
            for field in (
                "seconds",
                "reported_cost",
                "observed_model_steps",
                "server_start_seconds",
                "output_words",
                "check_count",
                "failed_check_count",
            )
        },
    }


def summarize(output, frozen):
    with output_lock(output):
        index = build_index(output, frozen)
        report = {
            "stage": frozen["stage"],
            "manifest_sha256": frozen["manifest_sha256"],
            "counts": status_counts(index),
            "usage": {},
            "execution": [],
            "notes": [
                "First-attempt validity is the headline; selected retries are reported separately.",
                "Failed and interrupted attempts are retained; missing usage is unknown.",
                "Adapter seconds include startup/cleanup; native server timing is partial metadata.",
                "Invocation wall time is elapsed batch time, not summed adapter seconds.",
                "Provider attempts are unavailable; reported cost is not subscription billing.",
                "Descriptive execution metadata only; outcome statistics require separate analysis.",
            ],
        }
        for split in (*SPLITS, "all"):
            report["usage"][split] = {}
            for role, jobs in index["jobs"].items():
                entries = [
                    item
                    for item in jobs.values()
                    if split == "all" or item["split"] == split
                ]
                first = [item["attempts"][0] for item in entries if item["attempts"]]
                retries = [
                    attempt for item in entries for attempt in item["attempts"][1:]
                ]
                selected = [
                    attempt
                    for item in entries
                    for attempt in item["attempts"]
                    if attempt["attempt"] == item["selected_first_valid"]
                ]
                report["usage"][split][role] = {
                    "first_attempt": usage(first),
                    "retained_retries": usage(retries),
                    "all_attempts": usage(first + retries),
                    "selected_first_valid": usage(selected),
                    "first_attempt_validity_rate": (
                        sum(item["status"] == "valid" for item in first) / len(first)
                    )
                    if first
                    else None,
                }
        for path in sorted((output / "invocations").glob("*.json")):
            if path.name.endswith(".finished.json"):
                continue
            invocation = read_json(path)
            finish = path.with_name(path.stem + ".finished.json")
            report["execution"].append(
                {**invocation, "finish": read_json(finish) if finish.exists() else None}
            )
        save_cache(output / "jobindex.json", index)
        save_cache(output / "summary.json", report)
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "validate",
        help="Validate the exact full suite without displaying case contents",
    )
    init = commands.add_parser(
        "init", help="Freeze every job and run metadata-only preflight"
    )
    init.add_argument("--output", type=Path, required=True)
    init.add_argument("--seed", type=int, default=base.SEED)
    init.add_argument("--timeout", type=int, default=600)
    init.add_argument("--max-attempts", type=int, choices=(1, 2), default=2)
    for name in ("writers", "judges", "status", "summarize"):
        command = commands.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
        if name in ("writers", "judges"):
            command.add_argument(
                "--split", choices=(*SPLITS, "all"), default="development"
            )
            command.add_argument("--limit", type=int)
            command.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            inputs = load_inputs()
            schedule = make_schedule(
                inputs["cases"], inputs["case_metadata"], base.SEED
            )
            print(
                json_text(
                    {
                        "valid": True,
                        "cases": len(inputs["cases"]),
                        "categories": len(CATEGORIES),
                        "development": 12,
                        "holdout": 24,
                        "jobs": {role: len(jobs) for role, jobs in schedule.items()},
                    }
                ),
                end="",
            )
            return 0
        output = args.output.resolve()
        exit_code = 0
        if args.command == "init":
            frozen = initialize(output, args.seed, args.timeout, args.max_attempts)
            report = {
                "ready": True,
                "manifest_sha256": frozen["manifest_sha256"],
                "jobs": {role: len(jobs) for role, jobs in frozen["jobs"].items()},
            }
        else:
            frozen = load_frozen(output)
            if args.command in ("writers", "judges"):
                report = run_jobs(
                    output,
                    frozen,
                    args.command,
                    args.split,
                    args.limit,
                    args.concurrency,
                )
                counts = report[args.split][args.command]
                exit_code = 1 if counts["failed"] or counts["blocked"] else 0
            else:
                report = (status if args.command == "status" else summarize)(
                    output, frozen
                )
        print(json_text(report), end="")
        return exit_code
    except KeyboardInterrupt:
        print("Interrupted; attempts and invocation timing retained.", file=sys.stderr)
        return 130
    except (ValueError, OSError, KeyError, TypeError) as error:
        # Only our own ValueErrors have text-safe messages. Other exception
        # bodies (including missing paths) are not useful case-safe diagnostics.
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        print("Error: " + message, file=sys.stderr)
        return 1


if __name__ == "__main__":

    def terminate(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    sys.exit(main())
