#!/usr/bin/env python3
"""Run controlled, text-only OpenCode documentation experiments (Python 3.9+)."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import shutil
import signal
import statistics
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SKILL = ROOT / "skills/engineering-standard/SKILL.md"
REFERENCE = SKILL.parent / "references/documenting/README.md"
RULE_PREFIX = "- After creating or updating documentation,"
VERSION = "1.18.31"
WRITER_MODEL = "openai/gpt-6-astra"
JUDGE_MODEL = "github-copilot/claude-sonnet-5"
WRITER_VARIANT = "high"
TOKEN_LIMIT = 16000
SEED = 46075


def read_json(path):
    return json.loads(Path(path).read_text())


def save_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def check_output(case, text):
    results = []
    for check in case["checks"]:
        kind, value = check["kind"], check["value"]
        if kind == "contains":
            passed = value in text
        elif kind == "not_contains":
            passed = value not in text
        elif kind == "count_at_least":
            passed = text.count(value) >= check["minimum"]
        elif kind == "regex":
            passed = re.search(value, text) is not None
        else:
            raise ValueError("Unknown check: " + kind)
        results.append({**check, "passed": passed})
    # These syntax checks cover fenced JSON only. Synthetic CLI examples cannot
    # be executed against a real product, and literal checks are semantic proxies.
    for i, block in enumerate(re.findall(r"^```json\s*\n(.*?)^```", text, re.M | re.S)):
        try:
            json.loads(block)
            passed = True
        except ValueError:
            passed = False
        results.append({"id": "json-block-" + str(i), "passed": passed})
    return results


def load_cases():
    cases = [read_json(p) for p in sorted((HERE / "cases/calibration").glob("*.json"))]
    if len(cases) != 3 or len({c["id"] for c in cases}) != 3:
        raise ValueError("Calibration requires exactly three distinct cases")
    for case in cases:
        for field in ("id", "family", "task", "source_facts", "draft"):
            if not isinstance(case[field], str) or not case[field].strip():
                raise ValueError("Missing case field: " + field)
        for field in ("requirements", "issues", "checks"):
            ids = [item["id"] for item in case[field]]
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate annotation IDs")
        requirements = {r["id"] for r in case["requirements"]}
        for check in case["checks"]:
            if check["requirement"] not in requirements:
                raise ValueError("Check references unknown requirement")
        if not all(c["passed"] for c in check_output(case, case["draft"])):
            raise ValueError("Original draft fails a preservation proxy: " + case["id"])
    return cases


def load_inputs():
    skill = SKILL.read_text()
    lines = skill.splitlines()
    rules = [line for line in lines if line.startswith(RULE_PREFIX)]
    if len(rules) != 1:
        raise ValueError("Expected one documentation rule in SKILL.md")
    base = "\n".join(line for line in lines if not line.startswith(RULE_PREFIX)) + "\n"
    reference = REFERENCE.read_text()
    # Exclude candidate status and research citations: neither is an instruction
    # under test, and exposing experimental framing could influence the writer.
    guidance = reference.split("## Review and revise\n", 1)[1].split("\n## Sources", 1)[
        0
    ]
    common = (HERE / "prompts/writer.md").read_text()
    return {
        "cases": load_cases(),
        "systems": {
            "A": common + "\n" + base,
            "B": common + "\n" + skill,
            "C": common + "\n" + skill + "\n## Documentation review\n" + guidance,
        },
        "judge_system": (HERE / "prompts/judge.md").read_text(),
        "source_hashes": {
            str(p.relative_to(ROOT)): digest(p.read_text())
            for p in (
                SKILL,
                REFERENCE,
                HERE / "prompts/writer.md",
                HERE / "prompts/judge.md",
                Path(__file__),
            )
        },
    }


def initialize(output):
    inputs = load_inputs()
    manifest = output / "manifest.json"
    if manifest.exists():
        frozen = read_json(manifest)
        if frozen["inputs"] != inputs:
            raise ValueError("Inputs or runner changed; use a new output directory")
        return frozen
    output.mkdir(parents=True, exist_ok=True)
    jobs = [(c["id"], arm) for c in inputs["cases"] for arm in ("A", "B", "C")]
    random.Random(SEED).shuffle(jobs)
    frozen = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "calibration",
        "seed": SEED,
        "writer_model": WRITER_MODEL,
        "writer_variant": WRITER_VARIANT,
        "judge_model": JUDGE_MODEL,
        "judge_variant": "provider default",
        "output_token_limit_requested": TOKEN_LIMIT,
        "opencode_version_required": VERSION,
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "inputs": inputs,
        "writer_order": jobs,
        "limitations": [
            "Single-session finalization, not externally enforced generate/critique/rewrite passes.",
            "Custom text-only agent; normal build-agent behavior and skill discovery are not evaluated.",
            "Provider defaults and built-in authentication transforms remain version-dependent.",
            "OAuth-reported cost may not represent actual subscription usage or billing.",
        ],
    }
    save_json(manifest, frozen)
    return frozen


def configuration(system, model):
    return {
        "$schema": "https://opencode.ai/config.json",
        "model": model,
        "default_agent": "documentation-eval",
        "autoupdate": False,
        "share": "disabled",
        "snapshot": False,
        "formatter": False,
        "lsp": False,
        "instructions": [],
        "plugin": [],
        "mcp": {},
        "permission": {"*": "deny"},
        "compaction": {"auto": False, "prune": False},
        "enabled_providers": [model.split("/", 1)[0]],
        "agent": {
            "documentation-eval": {
                "description": "Controlled text-only documentation evaluation",
                "mode": "primary",
                "model": model,
                "prompt": system,
                "permission": {"*": "deny"},
                "steps": 2,
            }
        },
    }


@contextmanager
def isolated_runtime(config):
    executable = shutil.which("opencode")
    if not executable:
        raise ValueError("opencode executable not found")
    host_home = Path.home()
    # Keep existing authentication in OpenCode's data directory. It is never
    # read, copied, printed, or written by this runner. Model tools are denied.
    data = os.environ.get("XDG_DATA_HOME", str(host_home / ".local/share"))
    cache = os.environ.get("XDG_CACHE_HOME", str(host_home / ".cache"))
    allowed = (
        "PATH",
        "LANG",
        "LC_ALL",
        "TMPDIR",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "NODE_EXTRA_CA_CERTS",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "NO_PROXY",
    )
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    with tempfile.TemporaryDirectory(
        prefix="documenting-eval-", dir=Path(tempfile.gettempdir()) / "opencode"
    ) as tmp:
        root = Path(tmp)
        for name in ("home", "config", "state", "work"):
            (root / name).mkdir()
        env.update(
            {
                "HOME": str(root / "home"),
                "XDG_CONFIG_HOME": str(root / "config"),
                "XDG_STATE_HOME": str(root / "state"),
                "XDG_DATA_HOME": data,
                "XDG_CACHE_HOME": cache,
                "OPENCODE_CONFIG_DIR": str(root / "config/opencode"),
                "OPENCODE_CONFIG_CONTENT": json.dumps(config),
                "OPENCODE_DISABLE_PROJECT_CONFIG": "1",
                "OPENCODE_DISABLE_CLAUDE_CODE": "1",
                "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
                "OPENCODE_DISABLE_CLAUDE_CODE_SKILLS": "1",
                "OPENCODE_DISABLE_AUTOUPDATE": "1",
                "OPENCODE_DISABLE_AUTOCOMPACT": "1",
                "OPENCODE_DISABLE_PRUNE": "1",
                "OPENCODE_DISABLE_LSP_DOWNLOAD": "1",
                "OPENCODE_EXPERIMENTAL_DISABLE_FILEWATCHER": "1",
                "OPENCODE_PURE": "1",
                "OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX": str(TOKEN_LIMIT),
            }
        )
        yield executable, root / "work", env


def execute(command, cwd, env, timeout, input_text=None):
    start = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(input=input_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
    return stdout, stderr, process.returncode, timed_out, time.monotonic() - start


def preflight(output, frozen):
    config = configuration(frozen["inputs"]["systems"]["A"], WRITER_MODEL)
    with isolated_runtime(config) as (exe, cwd, env):
        version = subprocess.check_output(
            [exe, "--version"], env=env, cwd=cwd, text=True, stdin=subprocess.DEVNULL
        ).strip()
        if version != VERSION:
            raise ValueError("Expected OpenCode " + VERSION + ", got " + version)
        inspections = {}
        for name, args in (
            ("paths", ["debug", "paths"]),
            ("config", ["debug", "config"]),
            ("agent", ["debug", "agent", "documentation-eval"]),
            ("skills", ["debug", "skill"]),
        ):
            stdout, stderr, code, timed_out, duration = execute(
                [exe, *args, "--pure"], cwd, env, 60
            )
            (output / ("preflight-" + name + ".txt")).write_text(stdout)
            if code or timed_out:
                raise ValueError("Preflight failed: " + name + ": " + stderr[-2000:])
            inspections[name] = stdout
        resolved = json.loads(inspections["config"])
        agent = json.loads(inspections["agent"])
        if (
            resolved.get("instructions")
            or resolved.get("mcp")
            or resolved.get("plugin")
        ):
            raise ValueError(
                "Unexpected inherited instructions/plugins/MCP configuration"
            )
        if agent["prompt"] != config["agent"]["documentation-eval"]["prompt"]:
            raise ValueError("Effective agent prompt differs from the assigned prompt")
        # OpenCode retains earlier default allow rules; later deny rules override
        # them. Its debug command resolves aliases and last-match precedence.
        if not agent.get("tools") or any(agent["tools"].values()):
            raise ValueError("Effective agent tools are not all disabled")
        # Built-in skills may still be advertised by OpenCode. Persist the list
        # and require that no user/project skill paths leaked into it.
        if str(Path.home()) in inspections["skills"]:
            raise ValueError("Host skills leaked into isolated runtime")
        checks = {
            "version": version,
            "prompt_matches": True,
            "all_resolved_tools_disabled": True,
            "no_configured_instructions_plugins_mcp": True,
            "duration_kind": "includes CLI startup",
        }
    metadata = {}
    for role, model, system in (
        ("writer", WRITER_MODEL, frozen["inputs"]["systems"]["A"]),
        ("judge", JUDGE_MODEL, frozen["inputs"]["judge_system"]),
    ):
        with isolated_runtime(configuration(system, model)) as (exe, cwd, env):
            stdout, stderr, code, timed_out, _ = execute(
                [exe, "models", model.split("/", 1)[0], "--verbose", "--pure"],
                cwd,
                env,
                60,
            )
            marker = re.search(r"(?m)^" + re.escape(model) + r"\r?$", stdout)
            if code or timed_out or marker is None:
                raise ValueError(
                    "Model metadata unavailable: " + model + ": " + stderr[-1000:]
                )
            item, _ = json.JSONDecoder().raw_decode(stdout[marker.end() :].lstrip())
            metadata[role] = {
                key: item.get(key)
                for key in (
                    "id",
                    "providerID",
                    "name",
                    "limit",
                    "capabilities",
                    "options",
                    "variants",
                    "cost",
                )
            }
            agent_out, stderr, code, timed_out, _ = execute(
                [exe, "debug", "agent", "documentation-eval", "--pure"], cwd, env, 60
            )
            if code or timed_out:
                raise ValueError("Agent inspection failed: " + role)
            agent = json.loads(agent_out)
            if (
                agent["prompt"] != system
                or not agent.get("tools")
                or any(agent["tools"].values())
            ):
                raise ValueError("Unexpected effective prompt/tools: " + role)
            if agent["model"] != {
                "providerID": model.split("/", 1)[0],
                "modelID": model.split("/", 1)[1],
            }:
                raise ValueError("Unexpected effective model: " + role)
            (output / ("preflight-" + role + "-agent.txt")).write_text(agent_out)
    if WRITER_VARIANT not in (metadata["writer"]["variants"] or {}):
        raise ValueError("Writer reasoning variant is unavailable")
    checks["models"] = metadata
    checks["writer_variant_supported"] = WRITER_VARIANT
    checks["output_limit"] = (
        "Requested via runtime flag; provider-side enforcement not verified"
    )
    save_json(output / "preflight.json", checks)
    print(
        "Preflight passed: pinned CLI, controlled prompt/configuration, denied tools."
    )


def parse_events(stdout):
    events, noise = [], []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            noise.append(line)
            continue
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            events.append(
                {"type": "malformed", "description": "Invalid event envelope"}
            )
            continue
        # Store visible outputs and usage, never reasoning blocks.
        if event["type"] == "reasoning":
            continue
        if event["type"] == "text" and (
            not isinstance(event.get("part"), dict)
            or not isinstance(event["part"].get("text"), str)
        ):
            events.append({"type": "malformed", "description": "Invalid text event"})
            continue
        if event["type"] == "step_finish":
            part = event.get("part")
            if not isinstance(part, dict):
                events.append(
                    {"type": "malformed", "description": "Missing usage part"}
                )
                continue
            tokens = part.get("tokens")
            if not isinstance(tokens, dict) or not isinstance(
                tokens.get("cache", {}), dict
            ):
                events.append(
                    {"type": "malformed", "description": "Invalid usage event"}
                )
                continue
            numbers = [tokens.get(key, 0) for key in ("input", "output", "reasoning")]
            numbers += [
                tokens.get("cache", {}).get(key, 0) for key in ("read", "write")
            ]
            numbers += [part.get("cost", 0)]
            if any(type(n) not in (int, float) or n < 0 for n in numbers):
                events.append(
                    {"type": "malformed", "description": "Invalid usage numbers"}
                )
                continue
        events.append(event)
    return events, noise


def event_metrics(events):
    totals = {
        "input": 0,
        "output": 0,
        "reasoning": 0,
        "cache_read": 0,
        "cache_write": 0,
    }
    steps, cost, finishes = 0, 0.0, []
    for event in events:
        if event.get("type") != "step_finish":
            continue
        steps += 1
        part = event["part"]
        finishes.append(part.get("reason"))
        cost += part.get("cost", 0) or 0
        tokens = part.get("tokens", {})
        for key in ("input", "output", "reasoning"):
            totals[key] += tokens.get(key, 0) or 0
        for key in ("read", "write"):
            totals["cache_" + key] += tokens.get("cache", {}).get(key, 0) or 0
    return {
        "tokens": totals,
        "observed_model_steps": steps,
        "reported_cost": cost,
        "finish_reasons": finishes,
        "provider_attempts": "unavailable; CLI may retry internally",
    }


def call_model(folder, system, prompt, model, variant, timeout):
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "system.md").write_text(system)
    (folder / "input.md").write_text(prompt)
    config = configuration(system, model)
    save_json(folder / "config.json", config)
    with isolated_runtime(config) as (exe, cwd, env):
        args = [
            exe,
            "run",
            "--pure",
            "--agent",
            "documentation-eval",
            "--model",
            model,
            "--format",
            "json",
            "--title",
            "documentation-eval",
        ]
        if variant:
            args += ["--variant", variant]
        # v1.18.31 re-quotes positional prompts. With no positional message its
        # stdin path transmits the supplied UTF-8 text without that transformation.
        stdout, stderr, code, timed_out, duration = execute(
            args, cwd, env, timeout, input_text=prompt
        )
    events, noise = parse_events(stdout)
    text = "\n".join(e["part"]["text"] for e in events if e.get("type") == "text")
    (folder / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    (folder / "stderr.txt").write_text(stderr)
    (folder / "stdout-noise.txt").write_text("\n".join(noise))
    (folder / "output.md").write_text(text)
    metrics = event_metrics(events)
    failures = []
    if code != 0 or timed_out:
        failures.append("CLI exit or timeout")
    if any(e.get("type") in ("tool_use", "error", "malformed") for e in events):
        failures.append("tool call, error, or malformed event")
    if not text.strip() or metrics["observed_model_steps"] != 1:
        failures.append("empty response or unexpected model step count")
    if any(reason not in ("stop", "end_turn") for reason in metrics["finish_reasons"]):
        failures.append("unexpected finish reason")
    result = {
        "status": "failed" if failures else "completed",
        "failures": failures,
        "model": model,
        "variant": variant,
        "seconds": duration,
        "exit_code": code,
        "timed_out": timed_out,
        "session_ids": sorted({e["sessionID"] for e in events if "sessionID" in e}),
        "system_sha256": digest(system),
        "input_sha256": digest(prompt),
        "output_sha256": digest(text),
        "output_words": len(text.split()),
        **metrics,
    }
    save_json(folder / "result.json", result)
    return result, text


def existing(folder):
    if not folder.exists():
        return False
    result = folder / "result.json"
    if not result.exists() or read_json(result)["status"] != "completed":
        raise ValueError(
            "Failed/incomplete trial retained; inspect and use a new run: "
            + str(folder)
        )
    return True


def writer_prompt(case):
    return (
        "# Task\n"
        + case["task"]
        + "\n\n# Source facts\n"
        + case["source_facts"]
        + "\n\n# Original draft\n"
        + case["draft"]
    )


def writers(output, frozen, concurrency, limit, timeout):
    cases = {c["id"]: c for c in frozen["inputs"]["cases"]}
    jobs = [
        (case, arm)
        for case, arm in frozen["writer_order"]
        if not existing(output / "writers" / (case + "-" + arm))
    ]
    if limit:
        jobs = jobs[:limit]

    def work(job):
        case_id, arm = job
        case = cases[case_id]
        folder = output / "writers" / (case_id + "-" + arm)
        result, text = call_model(
            folder,
            frozen["inputs"]["systems"][arm],
            writer_prompt(case),
            WRITER_MODEL,
            WRITER_VARIANT,
            timeout,
        )
        checks = check_output(case, text)
        save_json(folder / "checks.json", checks)
        print(
            "writer",
            case_id,
            arm,
            result["status"],
            round(result["seconds"], 1),
            "seconds",
            flush=True,
        )
        return result["status"] == "completed"

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(work, jobs))
    if not all(results):
        raise ValueError("One or more writers failed; inspect recorded artifacts")


def validate_judgment(value, case):
    if not isinstance(value, dict) or set(value) != {"candidates", "winner", "reason"}:
        raise ValueError("Unexpected judge response fields")
    if value["winner"] not in ("left", "right", "tie", "uncertain") or not isinstance(
        value["reason"], str
    ):
        raise ValueError("Invalid winner or reason")
    if not isinstance(value["candidates"], dict) or set(value["candidates"]) != {
        "left",
        "right",
    }:
        raise ValueError("Expected left and right candidates")
    for side in value["candidates"].values():
        if not isinstance(side, dict) or set(side) != {
            "requirements",
            "issues",
            "regressions",
            "organization",
            "unnecessary_change",
        }:
            raise ValueError("Unexpected candidate fields")
        for kind, statuses in (
            ("requirements", {"pass", "fail", "uncertain"}),
            ("issues", {"resolved", "partial", "unresolved", "uncertain"}),
        ):
            if not isinstance(side[kind], list):
                raise ValueError("Judge annotations must be arrays")
            expected = {item["id"] for item in case[kind]}
            received = [item["id"] for item in side[kind]]
            if len(received) != len(set(received)) or set(received) != expected:
                raise ValueError("Incomplete or duplicate judge annotation IDs")
            for item in side[kind]:
                if (
                    set(item) != {"id", "status", "evidence"}
                    or item["status"] not in statuses
                ):
                    raise ValueError("Invalid assessment")
                if (
                    not isinstance(item["evidence"], str)
                    or not item["evidence"].strip()
                ):
                    raise ValueError("Missing assessment evidence")
        if not isinstance(side["regressions"], list):
            raise ValueError("Judge regressions must be an array")
        for regression in side["regressions"]:
            if set(regression) != {"severity", "description", "evidence"}:
                raise ValueError("Invalid regression fields")
            if regression["severity"] not in ("critical", "major", "minor"):
                raise ValueError("Invalid regression severity")
            if any(
                not isinstance(regression[field], str) or not regression[field].strip()
                for field in ("description", "evidence")
            ):
                raise ValueError("Missing regression description or evidence")
        for field, lower, upper in (
            ("organization", 1, 5),
            ("unnecessary_change", 0, 3),
        ):
            if type(side[field]) is not int or not lower <= side[field] <= upper:
                raise ValueError("Invalid judge score")


def judge(output, frozen, concurrency, limit, timeout):
    jobs = []
    for case in frozen["inputs"]["cases"]:
        for first, second in (("A", "B"), ("B", "C")):
            for left, right in ((first, second), (second, first)):
                name = case["id"] + "-" + left + right
                if not existing(output / "judges" / name):
                    jobs.append((case, left, right, name))
    random.Random(SEED + 1).shuffle(jobs)
    if limit:
        jobs = jobs[:limit]

    def work(job):
        case, left, right, name = job
        documents = {}
        for label, arm in (("left", left), ("right", right)):
            writer = output / "writers" / (case["id"] + "-" + arm)
            if not existing(writer):
                raise ValueError("Missing writer for " + name)
            documents[label] = (writer / "output.md").read_text()
        payload = {
            key: case[key]
            for key in ("task", "source_facts", "draft", "requirements", "issues")
        }
        payload["candidates"] = documents
        folder = output / "judges" / name
        result, text = call_model(
            folder,
            frozen["inputs"]["judge_system"],
            json.dumps(payload, indent=2),
            JUDGE_MODEL,
            None,
            timeout,
        )
        save_json(
            folder / "mapping.json", {"case": case["id"], "left": left, "right": right}
        )
        if result["status"] == "completed":
            try:
                value = json.loads(text)
                validate_judgment(value, case)
                save_json(folder / "judgment.json", value)
            except (ValueError, KeyError, TypeError) as error:
                result["status"] = "failed"
                result["failures"].append("Invalid judge JSON: " + str(error))
                save_json(folder / "result.json", result)
        print(
            "judge",
            name,
            result["status"],
            round(result["seconds"], 1),
            "seconds",
            flush=True,
        )
        return result["status"] == "completed"

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(work, jobs))
    if not all(results):
        raise ValueError("One or more judges failed; inspect recorded artifacts")


def summarize(output, frozen):
    summary = {"stage": "calibration", "usage": {}, "writers": [], "comparisons": []}
    for kind in ("writers", "judges"):
        results = [read_json(p) for p in sorted((output / kind).glob("*/result.json"))]
        summary["usage"][kind] = {
            "sessions": len(results),
            "completed": sum(r["status"] == "completed" for r in results),
            "observed_model_steps": sum(r["observed_model_steps"] for r in results),
            "total_seconds": sum(r["seconds"] for r in results),
            "mean_seconds": statistics.mean(r["seconds"] for r in results)
            if results
            else None,
            "reported_cost": sum(r["reported_cost"] for r in results),
            "tokens": {
                key: sum(r["tokens"][key] for r in results)
                for key in ("input", "output", "reasoning", "cache_read", "cache_write")
            },
        }
    for case in frozen["inputs"]["cases"]:
        for arm in ("A", "B", "C"):
            folder = output / "writers" / (case["id"] + "-" + arm)
            if not (folder / "result.json").exists():
                continue
            result = read_json(folder / "result.json")
            summary["writers"].append(
                {
                    "case": case["id"],
                    "arm": arm,
                    "status": result["status"],
                    "original_words": len(case["draft"].split()),
                    "output_words": result["output_words"],
                    "failed_checks": [
                        c["id"]
                        for c in read_json(folder / "checks.json")
                        if not c["passed"]
                    ],
                }
            )
        for first, second in (("A", "B"), ("B", "C")):
            votes = []
            for left, right in ((first, second), (second, first)):
                folder = output / "judges" / (case["id"] + "-" + left + right)
                if not (folder / "judgment.json").exists():
                    continue
                judgment = read_json(folder / "judgment.json")
                winner = {"left": left, "right": right}.get(
                    judgment["winner"], judgment["winner"]
                )
                votes.append(
                    {
                        "order": left + right,
                        "winner": winner,
                        "reason": judgment["reason"],
                    }
                )
            summary["comparisons"].append(
                {
                    "case": case["id"],
                    "pair": first + second,
                    "votes": votes,
                    "order_agrees": len(votes) == 2
                    and votes[0]["winner"] == votes[1]["winner"],
                }
            )
    projections = {}
    for kind, count in (("writers", 324), ("judges", 270)):
        usage = summary["usage"][kind]
        if usage["sessions"]:
            ratio = count / usage["sessions"]
            projections[kind] = {
                "sessions": count,
                "serial_hours": usage["total_seconds"] * ratio / 3600,
                "tokens": {
                    key: value * ratio for key, value in usage["tokens"].items()
                },
                "reported_cost_projection_not_billing": usage["reported_cost"] * ratio,
            }
    summary["full_suite_projection"] = projections
    summary["interpretation"] = (
        "Calibration only. No efficacy, significance, or universal improvement claim."
    )
    save_json(output / "summary.json", summary)
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("validate", "preflight", "writers", "judge", "summarize")
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    if (
        args.concurrency < 1
        or args.timeout < 1
        or (args.limit is not None and args.limit < 1)
    ):
        parser.error("concurrency, limit, and timeout must be positive")
    if args.command == "validate":
        inputs = load_inputs()
        print("Validated", len(inputs["cases"]), "cases and three prompt variants.")
        return
    if not args.output:
        parser.error("--output is required")
    output = args.output.resolve()
    frozen = initialize(output)
    if args.command == "preflight":
        preflight(output, frozen)
    elif args.command == "summarize":
        summarize(output, frozen)
    else:
        if not (output / "preflight.json").exists():
            parser.error("Run preflight first")
        action = writers if args.command == "writers" else judge
        action(output, frozen, args.concurrency, args.limit, args.timeout)


if __name__ == "__main__":
    main()
