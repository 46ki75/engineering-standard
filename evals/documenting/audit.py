#!/usr/bin/env python3
"""Audit trial integrity independently of response validity using read-only exports."""

# fmt: off
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
import time

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("documenting_run", Path(__file__).resolve().with_name("run.py"))
assert spec is not None and spec.loader is not None
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
ERRORS = (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError)


def text(path):
    # Preserve line endings for exact hashes and transport comparisons.
    return path.read_bytes().decode("utf-8")


def check(report, name, passed):
    report.setdefault("checks", {})[name] = bool(passed)
    if not passed:
        report["errors"].append(name)


def export_json(stdout):
    # v1.18.31 cli/cmd/export.ts emits {info, messages}; tolerate console prefixes.
    for match in re.finditer(r"\{", stdout):
        try:
            value, end = json.JSONDecoder().raw_decode(stdout, match.start())
        except ValueError:
            continue
        if (isinstance(value, dict) and isinstance(value.get("info"), dict)
                and isinstance(value.get("messages"), list) and not stdout[end:].strip()):
            return value
    raise ValueError("Missing session JSON")


def session_audit(report, system, prompt, model, variant, session_id):
    with run.isolated_runtime(run.configuration(system, model)) as (exe, cwd, env):
        stdout, stderr, code, timeout, _ = run.execute(
            [exe, "export", session_id, "--pure"], cwd, env, 60)
    # Never retain CLI output or exception messages: either could contain reasoning.
    report["export"] = {"exit_code": code, "timed_out": timeout,
                        "stdout_chars": len(stdout), "stderr_chars": len(stderr)}
    check(report, "export_succeeded", code == 0 and not timeout)
    if code or timeout:
        return
    data = export_json(stdout)
    del stdout, stderr
    check(report, "export_session_matches", data["info"].get("id") == session_id)
    messages = data["messages"]
    check(report, "export_message_sessions_match",
          bool(messages) and all(m["info"].get("sessionID") == session_id for m in messages))
    users = [m for m in messages if m["info"]["role"] == "user"]
    user_text = ["".join(p["text"] for p in m["parts"] if p["type"] == "text") for m in users]
    check(report, "actual_user_input_matches", user_text == [prompt])
    check(report, "user_parts_text_only", all(p["type"] == "text" for m in users for p in m["parts"]))
    assistants = [m["info"] for m in messages if m["info"]["role"] == "assistant"]
    provider, model_id = model.split("/", 1)
    check(report, "actual_metadata_matches", bool(assistants) and all(
        (m.get("providerID"), m.get("modelID"), m.get("agent"))
        == (provider, model_id, "documentation-eval") for m in assistants))
    fields = ("providerID", "modelID", "agent", "variant")
    report["assistants"] = [{k: m[k] for k in fields if k in m and
                             (m[k] is None or isinstance(m[k], str) and len(m[k]) <= 200)} for m in assistants]
    requests = [m["info"]["model"]["variant"] for m in users if "variant" in m["info"].get("model", {})]
    requests += [m["info"]["variant"] for m in users if "variant" in m["info"]]
    variants = requests + [m["variant"] for m in assistants if "variant" in m]
    report["variant_request"] = ("matches" if all(v == variant for v in requests) else "mismatch") if requests else "not exposed"
    check(report, "exposed_variants_match", all(v == variant for v in variants))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    cutoff = time.time_ns()
    report = {"integrity": {"passed": None, "scope": "Artifact/session checks; passed and exit status exclude response validity"},
              "evaluation_response_validity": {"source": "Original result.json statuses; no revalidation or normalization"},
              "snapshot_utc": datetime.fromtimestamp(cutoff / 1e9, timezone.utc).isoformat(),
              "snapshot_policy": "result.json present and unmodified before cutoff; pending trials skipped",
              "errors": [], "skipped": [], "trials": []}
    snapshot = []
    try:
        # Freeze results before exports; newer completions belong to the next audit.
        for kind in ("writers", "judges"):
            for folder in sorted((output / kind).glob("*")):
                if not folder.is_dir():
                    continue
                name, path = str(folder.relative_to(output)), folder / "result.json"
                if not path.exists() or path.stat().st_mtime_ns > cutoff:
                    report["skipped"].append(name)
                    continue
                trial = {"trial": name, "errors": [], "checks": {
                    "actual_user_input_matches": None, "actual_metadata_matches": None}}
                report["trials"].append(trial)
                try:
                    raw = path.read_bytes()
                    if path.stat().st_mtime_ns > cutoff:
                        report["trials"].pop()
                        report["skipped"].append(name)
                        continue
                    result = json.loads(raw)
                    trial["result_status"] = result["status"]
                    failures = result["failures"]
                    # The runner changes status only after a normal call fails judge JSON validation.
                    trial["judge_schema_failure"] = (kind == "judges" and result["status"] == "failed"
                        and isinstance(failures, list) and bool(failures) and all(
                            isinstance(f, str) and f.startswith("Invalid judge JSON: ") for f in failures))
                    check(trial, "result_status_metadata", (result["status"] == "completed" and failures == [])
                          or trial["judge_schema_failure"])
                    snapshot.append((folder, result, trial))
                except ERRORS as error:
                    trial["errors"].append("result_metadata: " + type(error).__name__)
        manifest = run.read_json(output / "manifest.json")
        inputs = manifest["inputs"]
        check(report, "frozen_inputs_match", inputs == run.load_inputs())
        expected = {"writer_model": run.WRITER_MODEL, "judge_model": run.JUDGE_MODEL,
                    "writer_variant": run.WRITER_VARIANT, "judge_variant": "provider default",
                    "opencode_version_required": run.VERSION, "output_token_limit_requested": run.TOKEN_LIMIT}
        check(report, "manifest_configuration", all(manifest.get(k) == v for k, v in expected.items()))
        preflight = run.read_json(output / "preflight.json")
        check(report, "preflight", preflight["version"] == run.VERSION and all(preflight.get(k) is True for k in
              ("prompt_matches", "all_resolved_tools_disabled", "no_configured_instructions_plugins_mcp")))
        for role, model, system in (("writer", run.WRITER_MODEL, inputs["systems"]["A"]),
                                    ("judge", run.JUDGE_MODEL, inputs["judge_system"])):
            agent = run.read_json(output / ("preflight-" + role + "-agent.txt"))
            check(report, role + "_preflight_tools_prompt_model", bool(agent["tools"])
                  and all(v is False for v in agent["tools"].values()) and agent["prompt"] == system
                  and agent["name"] == "documentation-eval" and agent["model"] ==
                  dict(zip(("providerID", "modelID"), model.split("/", 1))))
        jobs = {(kind, c["id"] + "-" + arm): (c, arm) for c in inputs["cases"]
                for kind, arms in (("writers", ("A", "B", "C")), ("judges", ("AB", "BA", "BC", "CB"))) for arm in arms}
        seen, fixture_inputs = set(), {}
        for folder, result, trial in snapshot:
            stage = "stored_validation"
            try:
                ids = result["session_ids"]
                valid = isinstance(ids, list) and len(ids) == 1 and isinstance(ids[0], str) and re.fullmatch(r"ses_[A-Za-z0-9]+", ids[0])
                check(trial, "one_session_id", valid)
                if not valid:
                    continue
                trial["session_id"] = ids[0]
                check(trial, "unique_session_id", ids[0] not in seen)
                seen.add(ids[0])
                case, arm = jobs[(folder.parent.name, folder.name)]
                writer = folder.parent.name == "writers"
                model, variant = (run.WRITER_MODEL, run.WRITER_VARIANT) if writer else (run.JUDGE_MODEL, None)
                system, prompt, answer = (text(folder / (k + ".md")) for k in ("system", "input", "output"))
                assigned = inputs["systems"][arm] if writer else inputs["judge_system"]
                if writer:
                    expected_prompt = run.writer_prompt(case)
                    check(trial, "identical_fixture_input_across_arms", fixture_inputs.setdefault(case["id"], prompt) == prompt)
                else:
                    payload = {k: case[k] for k in ("task", "source_facts", "draft", "requirements", "issues")}
                    payload["candidates"] = {side: text(output / "writers" / (case["id"] + "-" + a) / "output.md")
                                             for side, a in zip(("left", "right"), arm)}
                    expected_prompt = json.dumps(payload, indent=2)
                check(trial, "assigned_prompts", system == assigned and prompt == expected_prompt)
                check(trial, "stored_configuration", run.read_json(folder / "config.json") == run.configuration(system, model))
                check(trial, "result_metadata", result["model"] == model and result["variant"] == variant
                      and type(result["seconds"]) in (int, float) and math.isfinite(result["seconds"])
                      and result["seconds"] >= 0 and result["output_words"] == len(answer.split()) and bool(answer.strip()))
                for key, value in (("system", system), ("input", prompt), ("output", answer)):
                    check(trial, key + "_sha256", run.digest(value) == result[key + "_sha256"])
                events = [json.loads(line) for line in text(folder / "events.jsonl").splitlines() if line.strip()]
                check(trial, "no_recorded_reasoning_events", all(e.get("type") != "reasoning" and e.get("part", {}).get("type") != "reasoning" for e in events))
                check(trial, "no_tool_error_or_unknown_events", bool(events) and all(
                    e["type"] in ("text", "step_start", "step_finish") and e.get("part", {}).get("type") != "tool" for e in events))
                check(trial, "event_session_ids", all(e.get("sessionID") == ids[0] for e in events))
                check(trial, "event_output_matches", "\n".join(e["part"]["text"] for e in events if e["type"] == "text") == answer)
                metrics = run.event_metrics(events)
                check(trial, "result_event_metrics", all(result[k] == v for k, v in metrics.items()))
                numbers = [*metrics["tokens"].values(), metrics["reported_cost"]]
                check(trial, "valid_usage_numbers", all(type(n) in (int, float) and math.isfinite(n) and n >= 0 for n in numbers))
                normal = (result["exit_code"] == 0 and result["timed_out"] is False and bool(answer.strip())
                          and trial["checks"]["no_tool_error_or_unknown_events"]
                          and metrics["observed_model_steps"] == 1 and all(
                              r in ("stop", "end_turn") for r in metrics["finish_reasons"]))
                check(trial, "normal_model_completion", normal)
                if not normal or not trial["checks"]["result_status_metadata"]:
                    continue
                stage = "export_validation"
                session_audit(trial, system, prompt, model, variant, ids[0])
            except ERRORS as error:
                trial["errors"].append(stage + ": " + type(error).__name__)
    except ERRORS as error:
        report["errors"].append("audit_setup: " + type(error).__name__)
    report["passed"] = not report["errors"] and all(not t["errors"] for t in report["trials"])
    report["integrity"].update(passed=report["passed"], trials=len(report["trials"]), **{
        key: sum(t["checks"].get(key) is True for t in report["trials"])
        for key in ("actual_user_input_matches", "actual_metadata_matches")})
    judges = [t for t in report["trials"] if t["trial"].startswith("judges/")]
    report["evaluation_response_validity"].update(
        judge_result_status_counts={s: sum(t.get("result_status", "unavailable") == s for t in judges)
                                    for s in ("completed", "failed", "unavailable")},
        strict_schema_failures=[t["trial"] for t in judges if t.get("judge_schema_failure")])
    run.save_json(output / "audit.json", report)
    print(json.dumps({"passed": report["passed"], "trials": len(report["trials"]),
                      "skipped": len(report["skipped"]), "report": str(output / "audit.json")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
