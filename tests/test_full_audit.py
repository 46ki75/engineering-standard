"""Offline integrity tests using only synthetic fixtures and in-memory exports."""

from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[1] / "evals/documenting/full_audit.py"
SPEC = importlib.util.spec_from_file_location("_test_full_audit", SOURCE)
assert SPEC is not None and SPEC.loader is not None
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
full, run, structured = audit.full, audit.run, audit.structured
SECRET = "EPHEMERAL-REASONING-MUST-NEVER-BE-PERSISTED"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(full.json_text(value).encode("utf-8"))


class SyntheticRun:
    def __init__(self, root, count=2):
        self.root = root
        root.mkdir()
        cases = []
        for i in range(count):
            cases.append(
                {
                    "id": "synthetic-" + str(i),
                    "family": "PRIVATE-FAMILY",
                    "category": full.CATEGORIES[i // 6]
                    if count == 36
                    else "organization",
                    "split": "development"
                    if (i % 6 < 2 if count == 36 else i == 0)
                    else "holdout",
                    "task": "Revise the synthetic document.",
                    "source_facts": 'Alpha must be retained. A literal quote is "alpha".',
                    "draft": "Alpha retained.\r\nAn original synthetic document.",
                    "requirements": [
                        {"id": "r1", "text": "PRIVATE-ANNOTATION: retain Alpha."}
                    ],
                    "issues": [
                        {"id": "i1", "text": "PRIVATE-ISSUE: simplify wording."}
                    ],
                    "checks": [
                        {
                            "id": "c1",
                            "requirement": "r1",
                            "kind": "contains",
                            "value": "Alpha",
                        }
                    ],
                }
            )
        metadata = {}
        for case in cases:
            path = root.parent / (case["id"] + ".json")
            save(path, case)
            metadata[case["id"]] = {
                "category": case["category"],
                "split": case["split"],
                "source": path.name,
                "source_sha256": full.file_hash(path),
                "embedded_sha256": full.json_hash(case),
            }
        source = root.parent / "synthetic-source.py"
        source.write_bytes(b"# synthetic frozen source\r\n")
        self.frozen = full.make_manifest(
            {
                "cases": cases,
                "case_metadata": metadata,
                "systems": {
                    arm: "Synthetic guidance " + arm + ".\r\n" for arm in "ABC"
                },
                "judge_system": "Synthetic anonymous comparison instructions.",
                "judge_schemas": {
                    case["id"]: audit.judging.schema_for(case) for case in cases
                },
                "source_hashes": {source.name: full.file_hash(source)},
            },
            seed=19,
        )
        self.cases = {case["id"]: case for case in cases}
        self.writers = {job["id"]: job for job in self.frozen["jobs"]["writers"]}
        self.judges = {job["id"]: job for job in self.frozen["jobs"]["judges"]}
        self.selected = {}
        self.exports = {}
        self.serial = 0
        self.save_manifest()
        preflight = root / "preflights/synthetic/preflight.json"
        save(
            preflight,
            {
                "version": run.VERSION,
                "prompt_matches": True,
                "all_resolved_tools_disabled": True,
                "no_configured_instructions_plugins_mcp": True,
                "models": {
                    role: {
                        "id": model.split("/", 1)[1],
                        "providerID": model.split("/", 1)[0],
                        "variants": {"high": {}},
                    }
                    for role, model in (
                        ("writer", run.WRITER_MODEL),
                        ("judge", run.JUDGE_MODEL),
                    )
                },
            },
        )
        for role in ("writer", "judge"):
            model = self.frozen[role + "_model"]
            system = (
                self.frozen["inputs"]["systems"]["A"]
                if role == "writer"
                else self.frozen["inputs"]["judge_system"]
            )
            save(
                preflight.parent / ("preflight-" + role + "-agent.txt"),
                {
                    "name": "documentation-eval",
                    "prompt": system,
                    "tools": {"read": False},
                    "model": dict(zip(("providerID", "modelID"), model.split("/", 1))),
                },
            )
        save(
            root / "ready.json",
            {
                "manifest_sha256": self.frozen["manifest_sha256"],
                "preflight": str(preflight.relative_to(root)),
                "preflight_sha256": full.file_hash(preflight),
                "writer_variant": "high",
                "judge_variant": "high",
            },
        )
        for role in audit.ROLES:
            save(
                root / "invocations" / (role + ".json"),
                {
                    "id": role,
                    "manifest_sha256": self.frozen["manifest_sha256"],
                    "arguments": {"command": role},
                },
            )

    def save_manifest(self):
        self.frozen.pop("manifest_sha256", None)
        self.frozen["manifest_sha256"] = full.json_hash(self.frozen)
        save(self.root / "manifest.json", self.frozen)

    def folder(self, role, ident, number=1):
        return self.root / role / ident / ("attempt-" + str(number))

    def start(self, role, ident, number=1):
        folder = self.folder(role, ident, number)
        folder.mkdir(parents=True)
        save(
            folder.with_name(folder.name + ".started.json"),
            {
                "attempt": number,
                "invocation": role,
                "started_utc": "2026-09-16T00:00:00Z",
                "manifest_sha256": self.frozen["manifest_sha256"],
            },
        )
        return folder

    def judgment(self, documents):
        return {
            "winner": "tie",
            "reason": "Synthetic assessment.",
            "candidates": {
                side: {
                    "requirements": {
                        "r1": {
                            "status": "pass",
                            "quote": "Alpha retained.",
                            "explanation": "Synthetic evidence.",
                        }
                    },
                    "issues": {
                        "i1": {
                            "status": "resolved",
                            "quote": "",
                            "explanation": "Synthetic assessment.",
                        }
                    },
                    "regressions": [],
                    "organization": 4,
                    "unnecessary_change": 0,
                }
                for side in documents
            },
        }

    def attempt(
        self,
        role,
        ident,
        number=1,
        *,
        status="valid",
        kind=None,
        sid=None,
        value=None,
        protocol_failure=False,
        answer=None,
    ):
        self.serial += 1
        sid = sid or "ses_synthetic" + str(self.serial)
        folder = self.start(role, ident, number)
        job = (self.writers if role == "writers" else self.judges)[ident]
        case = self.cases[job["case"]]
        writer = role == "writers"
        model = self.frozen["writer_model" if writer else "judge_model"]
        system = (
            self.frozen["inputs"]["systems"][job["arm"]]
            if writer
            else self.frozen["inputs"]["judge_system"]
        )
        config = run.configuration(system, model)
        usage = {
            "cost": 0.125,
            "tokens": {
                "input": 100,
                "output": 25,
                "reasoning": 10,
                "cache": {"read": 50, "write": 0},
            },
        }
        if writer:
            prompt = run.writer_prompt(case)
            answer = (
                answer
                if answer is not None
                else "Alpha retained.\r\nRevision "
                + job["arm"]
                + " "
                + str(job["repetition"])
            )
            events = [
                {
                    "type": "step_start",
                    "sessionID": sid,
                    "part": {"type": "step-start", "sessionID": sid},
                },
                {
                    "type": "text",
                    "sessionID": sid,
                    "part": {"type": "text", "text": answer, "sessionID": sid},
                },
                {
                    "type": "step_finish",
                    "sessionID": sid,
                    "part": {
                        "type": "step-finish",
                        "sessionID": sid,
                        "reason": "stop",
                        **usage,
                    },
                },
            ]
            provider, model_id = model.split("/", 1)
            self.exports[sid] = {
                "info": {"id": sid},
                "messages": [
                    {
                        "info": {
                            "role": "user",
                            "id": "msg_user",
                            "sessionID": sid,
                            "agent": "documentation-eval",
                            "model": {
                                "providerID": provider,
                                "modelID": model_id,
                                "variant": "high",
                            },
                        },
                        "parts": [{"type": "text", "text": prompt}],
                    },
                    {
                        "info": {
                            "role": "assistant",
                            "id": "msg_assistant",
                            "parentID": "msg_user",
                            "sessionID": sid,
                            "agent": "documentation-eval",
                            "providerID": provider,
                            "modelID": model_id,
                            "variant": "high",
                        },
                        "parts": [
                            {"type": "reasoning", "text": SECRET},
                            {"type": "text", "text": answer},
                        ],
                    },
                ],
            }
        else:
            mapping = {
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
            }
            mapping["writers"] = {}
            documents = {}
            for side in ("left", "right"):
                writer_id = job[side + "_writer"]
                selected = self.selected[writer_id]
                path = self.folder("writers", writer_id, selected) / "output.md"
                documents[side] = audit.text(path)
                mapping["writers"][side] = {
                    "job": writer_id,
                    "attempt": selected,
                    "output_sha256": full.file_hash(path),
                }
            save(folder / "mapping.json", mapping)
            prompt = full.json_text(
                full.judge_payload(case, documents["left"], documents["right"])
            )
            permission = {"*": "deny", "StructuredOutput": "allow"}
            config["permission"] = permission
            config["agent"]["documentation-eval"]["permission"] = permission.copy()
            save(
                folder / "schema.json",
                self.frozen["inputs"]["judge_schemas"][case["id"]],
            )
            value = value if value is not None else self.judgment(documents)
            provider, model_id = model.split("/", 1)
            info = {
                "id": "msg_assistant",
                "parentID": "msg_user",
                "sessionID": sid,
                "role": "assistant",
                "providerID": provider,
                "modelID": model_id,
                "agent": "documentation-eval",
                "variant": "high",
                "time": {"created": 1, "completed": 2},
                "finish": "length" if protocol_failure else "tool-calls",
                **usage,
            }
            common = {"sessionID": sid, "messageID": "msg_assistant"}
            response = {
                "info": info,
                "parts": [
                    {"id": "prt_start", **common, "type": "step-start"},
                    {
                        "id": "prt_tool",
                        **common,
                        "type": "tool",
                        "tool": "StructuredOutput",
                        "state": {
                            "status": "completed",
                            "input": value,
                            "time": {"start": 1, "end": 2},
                            "metadata": {"valid": True},
                            "output": structured.TOOL_OUTPUT,
                        },
                    },
                    {
                        "id": "prt_finish",
                        **common,
                        "type": "step-finish",
                        "reason": "tool-calls",
                        **usage,
                    },
                ],
            }
            save(folder / "response.json", response)
            events = [
                {
                    "type": {
                        "step-start": "step_start",
                        "tool": "tool_use",
                        "step-finish": "step_finish",
                    }[p["type"]],
                    "sessionID": sid,
                    "part": p,
                }
                for p in response["parts"]
            ]
            answer = "" if protocol_failure else full.json_text(value)
            if not protocol_failure:
                save(folder / "structured.json", value)
            if status == "valid":
                save(folder / "judgment.json", value)
        for name, content in (
            ("system.md", system),
            ("input.md", prompt),
            ("output.md", answer),
        ):
            (folder / name).write_bytes(content.encode("utf-8"))
        save(folder / "config.json", config)
        (folder / "events.jsonl").write_bytes(
            "".join(json.dumps(e) + "\n" for e in events).encode("utf-8")
        )
        failed_transport = protocol_failure or kind == "transport"
        result = {
            "status": "failed" if failed_transport else "completed",
            "failures": ["Synthetic transport failure"] if failed_transport else [],
            "model": model,
            "variant": "high",
            "seconds": 1.25,
            "exit_code": 1 if failed_transport else 0,
            "timed_out": False,
            "session_ids": [sid],
            "output_words": len(answer.split()),
            **{
                name + "_sha256": full.file_hash(folder / (name + ".md"))
                for name in ("system", "input", "output")
            },
            **run.event_metrics(events),
        }
        if not writer:
            result.update(
                schema_sha256=full.file_hash(folder / "schema.json"),
                transport="opencode-http",
                input_audit_source="event_stream",
                actual_input_match=True,
                session_isolated=True,
                server_started=True,
                server_ready=True,
                prompt_posts=1,
                server_start_seconds=0.1,
                server_exit_code=0,
                abort_attempted=True,
                abort_succeeded=True,
                provider_attempts="unavailable; OpenCode may retry internally; adapter does not retry",
            )
        save(folder / "result.json", result)
        if writer:
            checks = run.check_output(case, answer)
            save(folder / "checks.json", checks)
            result = {
                **result,
                "check_count": len(checks),
                "failed_check_count": sum(not c["passed"] for c in checks),
            }
        failures = result["failures"] + (
            ["Judge schema or quote evidence validation failed"]
            if kind == "schema_or_evidence"
            else []
        )
        full.finalize_attempt(folder, result, status, kind, failures, 1.5)
        if writer and status == "valid":
            self.selected.setdefault(ident, number)
        return folder

    def all_writers(self):
        for ident in self.writers:
            self.attempt("writers", ident)

    def all_jobs(self):
        self.all_writers()
        for ident in self.judges:
            self.attempt("judges", ident)

    def recovery(self, root):
        recovered = SyntheticRun(root)
        recovered.frozen = deepcopy(self.frozen)
        recovered.frozen["judge_model"] = "synthetic/new-judge"
        script = root.parent / "evals/documenting/rejudge.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_bytes(b"# synthetic recovery source\n")
        recovered.frozen["recovery"] = {
            "script": "evals/documenting/rejudge.py",
            "script_sha256": full.file_hash(script),
            "source_output": str(self.root),
            "source_manifest_sha256": self.frozen["manifest_sha256"],
            "source_manifest_file_sha256": full.file_hash(self.root / "manifest.json"),
            "source_judge_model": self.frozen["judge_model"],
            "new_writer_calls": 0,
            "writer_jobs": len(self.writers),
            "writer_attempts": self.serial,
            "selected_writer_attempts": deepcopy(self.selected),
            "writer_artifact_sha256": audit.writer_archive_hashes(self.root),
            "reused_judge_attempts": 0,
            "fresh_judge_jobs": len(self.judges),
            "fresh_judge_splits": list(full.SPLITS),
        }
        shutil.copytree(self.root / "writers", root / "writers")
        recovered.selected, recovered.exports = (
            deepcopy(self.selected),
            deepcopy(self.exports),
        )
        recovered.serial = self.serial
        recovered.save_manifest()
        recovered.update_preflight()
        (root / "invocations/writers.json").unlink()
        save(
            root / "invocations/judges.json",
            {
                "id": "judges",
                "arguments": {"command": "judges"},
                "manifest_sha256": recovered.frozen["manifest_sha256"],
            },
        )
        return recovered

    def update_preflight(self):
        ready = full.read_json(self.root / "ready.json")
        path = self.root / ready["preflight"]
        preflight = full.read_json(path)
        for role in ("writer", "judge"):
            provider, model_id = self.frozen[role + "_model"].split("/", 1)
            preflight["models"][role].update(id=model_id, providerID=provider)
            agent_path = path.parent / ("preflight-" + role + "-agent.txt")
            agent = full.read_json(agent_path)
            agent["model"] = {"providerID": provider, "modelID": model_id}
            save(agent_path, agent)
        save(path, preflight)
        ready.update(
            manifest_sha256=self.frozen["manifest_sha256"],
            preflight_sha256=full.file_hash(path),
        )
        save(self.root / "ready.json", ready)

    @staticmethod
    def rehash(folder):
        outcome = full.read_json(folder / "outcome.json")
        outcome["artifact_sha256"] = {
            path.name: full.file_hash(path)
            for path in folder.iterdir()
            if path.is_file() and path.name != "outcome.json"
        }
        save(folder / "outcome.json", outcome)

    @staticmethod
    def change_record(folder, field, value, *, native=True, result=True, metrics=False):
        for name, enabled in (("native-result.json", native), ("result.json", result)):
            if enabled:
                record = full.read_json(folder / name)
                record[field] = value
                save(folder / name, record)
        if metrics:
            outcome = full.read_json(folder / "outcome.json")
            outcome["metrics"][field] = value
            save(folder / "outcome.json", outcome)
        SyntheticRun.rehash(folder)


class AuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="full-audit-offline-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.fixture = SyntheticRun(self.root / "run")
        self.executions = []
        self.configs = []
        self.mutex = threading.Lock()
        for target, name in (
            (socket, "socket"),
            (socket, "create_connection"),
            (run.subprocess, "Popen"),
            (run.subprocess, "check_output"),
            (full, "load_inputs"),
            (run, "load_inputs"),
            (run, "load_cases"),
            (full, "load_cases"),
            (run, "call_model"),
            (structured, "call_structured"),
        ):
            self.mock(
                target, name, side_effect=AssertionError("Offline boundary: " + name)
            )
        self.mock(audit.calibration.run, "isolated_runtime", side_effect=self.runtime)
        self.mock(audit.calibration.run, "execute", side_effect=self.execute)
        original = full.file_hash

        def confined_hash(path):
            self.assertTrue(
                Path(path).resolve().is_relative_to(self.root),
                "Attempt to read a real artifact/source",
            )
            return original(path)

        self.mock(full, "file_hash", side_effect=confined_hash)

    def mock(self, target, name, **kwargs):
        patcher = patch.object(target, name, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    @contextmanager
    def runtime(self, config):
        self.assertEqual(config["permission"], {"*": "deny"})
        self.assertEqual(config["instructions"], [])
        self.assertEqual(config["plugin"], [])
        self.assertEqual(config["mcp"], {})
        with self.mutex:
            self.configs.append(config)
            ident = len(self.configs)
        yield "stub-opencode", self.root / ("fresh-" + str(ident)), {}

    def execute(self, args, cwd, env, timeout):
        self.assertEqual(args[:2], ["stub-opencode", "export"])
        self.assertEqual(args[3:], ["--pure"])
        self.assertEqual(timeout, 60)
        with self.mutex:
            self.executions.append((args[2], cwd))
        return (
            "Exporting stored session\n" + json.dumps(self.fixture.exports[args[2]]),
            SECRET,
            0,
            False,
            0.1,
        )

    def audit(self, **kwargs):
        return audit.audit(self.fixture.root, **kwargs)

    def trial(self, report, folder):
        return next(
            t
            for t in report["attempts"]
            if t.get("folder") == str(folder.relative_to(self.fixture.root))
        )

    def assert_passed(self, report):
        self.assertTrue(
            report["passed"],
            (
                report["errors"],
                [(t["job"], t["errors"]) for t in report["attempts"] if t["errors"]],
            ),
        )

    def test_complete_594_jobs_use_324_fresh_exports_and_native_judges(self):
        self.fixture = SyntheticRun(self.root / "full", count=36)
        self.fixture.all_jobs()
        pool = self.mock(audit, "ThreadPoolExecutor", wraps=audit.ThreadPoolExecutor)
        report = self.audit(check_live_sources=True, source_root=self.root)
        self.assert_passed(report)
        self.assertTrue(report["complete"])
        self.assertEqual(report["counts"]["planned"], 594)
        self.assertEqual(report["counts"]["covered"], 594)
        self.assertEqual(report["counts"]["sessions"], 594)
        self.assertEqual(report["counts"]["writer_exports"], 324)
        self.assertEqual(report["counts"]["native_judge_sessions"], 270)
        self.assertEqual(len({cwd for _, cwd in self.executions}), 324)
        self.assertEqual(len({id(config) for config in self.configs}), 324)
        pool.assert_called_once_with(max_workers=6)
        self.assertNotIn(SECRET, json.dumps(report))

    def test_partial_and_ongoing_attempts_are_not_complete(self):
        ids = list(self.fixture.writers)
        self.fixture.attempt("writers", ids[0])
        self.fixture.start("writers", ids[1])
        report = self.audit()
        self.assertTrue(report["integrity"]["known_checks_passed"])
        self.assertIsNone(report["passed"])
        self.assertFalse(report["complete"])
        self.assertEqual(report["counts"]["ongoing"], 1)
        self.assertEqual(report["counts"]["ongoing_attempts"], 1)
        self.assertGreater(report["counts"]["pending"], 0)

    def test_failed_writer_is_exported_and_selected_retry_supplies_candidates(self):
        ident = next(iter(self.fixture.writers))
        failed = self.fixture.attempt(
            "writers", ident, status="failed", kind="transport", answer="Old candidate"
        )
        self.fixture.attempt("writers", ident, 2)
        for other in self.fixture.writers:
            if other != ident:
                self.fixture.attempt("writers", other)
        job = next(
            j
            for j in self.fixture.judges.values()
            if ident in (j["left_writer"], j["right_writer"])
        )
        folder = self.fixture.attempt("judges", job["id"])
        report = self.audit()
        self.assert_passed(report)
        self.assertEqual(
            self.trial(report, failed)["session_verification"], "cli_export"
        )
        self.assertEqual(
            report["counts"]["writer_exports"], len(self.fixture.writers) + 1
        )
        self.assertTrue(self.trial(report, folder)["checks"]["candidate_provenance"])
        self.assertEqual(report["jobs"]["writers"][ident]["selected_first_valid"], 2)

    def test_schema_failure_and_native_protocol_failure_do_not_imply_bad_input(self):
        self.fixture.all_writers()
        ids = list(self.fixture.judges)
        bad_schema = self.fixture.attempt(
            "judges",
            ids[0],
            status="failed",
            kind="schema_or_evidence",
            value={"bad": "schema"},
        )
        retry = self.fixture.attempt("judges", ids[0], 2)
        bad_protocol = self.fixture.attempt(
            "judges", ids[1], status="failed", kind="transport", protocol_failure=True
        )
        report = self.audit()
        self.assert_passed(report)
        self.assertEqual(
            report["evaluation_response_validity"]["schema_or_evidence_failures"], 1
        )
        for folder in (bad_schema, bad_protocol, retry):
            trial = self.trial(report, folder)
            self.assertEqual(trial["session_verification"], "native_sse")
            self.assertTrue(trial["checks"]["native_user_input_audit"])
        self.assertEqual(len(self.executions), len(self.fixture.writers))

    def test_preservation_failure_is_quality_not_integrity(self):
        folder = self.fixture.attempt(
            "writers",
            next(iter(self.fixture.writers)),
            answer="A revision with a preservation failure.",
        )
        report = self.audit()
        self.assert_passed(report)
        self.assertTrue(self.trial(report, folder)["checks"]["writer_check_metrics"])

    def test_manifest_own_hash_embedded_hash_and_schedule_are_checked(self):
        original = deepcopy(self.fixture.frozen)
        mutations = (
            (lambda m: m.update(seed=99), "manifest_own_hash", False),
            (
                lambda m: m["inputs"]["cases"][0].update(task="Changed"),
                "embedded_cases",
                True,
            ),
            (
                lambda m: m["jobs"]["judges"][0].update(left="C"),
                "frozen_schedule",
                True,
            ),
        )
        for mutate, expected, resign in mutations:
            with self.subTest(check=expected):
                self.fixture.frozen = deepcopy(original)
                mutate(self.fixture.frozen)
                if resign:
                    self.fixture.save_manifest()
                else:
                    save(self.fixture.root / "manifest.json", self.fixture.frozen)
                report = self.audit()
                self.assertFalse(report["checks"][expected])
                self.assertFalse(report["passed"])

    def test_live_source_check_is_optional_and_byte_exact(self):
        (self.root / "synthetic-source.py").write_bytes(b"# synthetic frozen source\n")
        self.assert_passed(self.audit())
        report = self.audit(check_live_sources=True, source_root=self.root)
        self.assertFalse(report["passed"])
        self.assertTrue(any(key.startswith("live_source_") for key in report["errors"]))

    def test_ready_hash_and_preflight_agent_are_verified(self):
        path = self.fixture.root / "preflights/synthetic/preflight-writer-agent.txt"
        value = full.read_json(path)
        value["tools"]["read"] = True
        save(path, value)
        report = self.audit()
        self.assertFalse(report["checks"]["writer_preflight_agent"])

    def test_artifact_hashes_and_all_native_metrics_are_checked(self):
        folder = self.fixture.attempt("writers", next(iter(self.fixture.writers)))
        self.fixture.change_record(
            folder,
            "tokens",
            {key: 999 for key in full.TOKENS},
            native=False,
            metrics=True,
        )
        (folder / "system.md").write_bytes(b"Changed system")
        report = self.audit()
        checks = self.trial(report, folder)["checks"]
        for name in (
            "native_result_fields",
            "native_outcome_metrics",
            "artifact_hash_system.md",
            "system_sha256",
            "assigned_system",
        ):
            self.assertFalse(checks[name])
        self.assertEqual(report["counts"]["writer_exports"], 1)

    def test_writer_exact_input_and_config_reject_annotation_leak(self):
        folder = self.fixture.attempt("writers", next(iter(self.fixture.writers)))
        prompt = audit.text(folder / "input.md") + "\nPRIVATE-ANNOTATION"
        (folder / "input.md").write_bytes(prompt.encode())
        self.fixture.change_record(folder, "input_sha256", run.digest(prompt))
        config = full.read_json(folder / "config.json")
        config["instructions"] = ["Injected guidance"]
        save(folder / "config.json", config)
        self.fixture.rehash(folder)
        report = self.audit()
        checks = self.trial(report, folder)["checks"]
        self.assertFalse(checks["assigned_input_without_labels"])
        self.assertFalse(checks["isolated_configuration"])

    def test_judge_candidate_sides_and_provenance_cannot_be_swapped(self):
        self.fixture.all_writers()
        job = next(j for j in self.fixture.judges.values() if j["kind"] == "swap")
        folder = self.fixture.attempt("judges", job["id"])
        payload = full.read_json(folder / "input.md")
        payload["candidates"]["left"], payload["candidates"]["right"] = (
            payload["candidates"]["right"],
            payload["candidates"]["left"],
        )
        payload["writer_role"] = "A"
        save(folder / "input.md", payload)
        self.fixture.change_record(
            folder, "input_sha256", full.file_hash(folder / "input.md")
        )
        mapping = full.read_json(folder / "mapping.json")
        mapping["writers"]["left"]["attempt"] = 2
        save(folder / "mapping.json", mapping)
        self.fixture.rehash(folder)
        report = self.audit()
        checks = self.trial(report, folder)["checks"]
        self.assertFalse(checks["assigned_input_without_labels"])
        self.assertFalse(checks["candidate_provenance"])

    def test_selected_quote_revalidation_and_native_judgment_equality(self):
        self.fixture.all_writers()
        folder = self.fixture.attempt("judges", next(iter(self.fixture.judges)))
        value = full.read_json(folder / "judgment.json")
        value["candidates"]["left"]["requirements"]["r1"]["quote"] = "Fabricated quote"
        save(folder / "judgment.json", value)
        self.fixture.rehash(folder)
        report = self.audit()
        trial = self.trial(report, folder)
        self.assertFalse(trial["checks"]["selected_judgment_matches_native"])
        self.assertFalse(trial["selected_schema_quote_valid"])
        self.assertTrue(trial["checks"]["native_user_input_audit"])
        self.assertEqual(
            report["evaluation_response_validity"][
                "selected_quote_validation_failures"
            ],
            1,
        )
        self.assertEqual(
            report["evaluation_response_validity"]["schema_or_evidence_failures"], 0
        )

    def test_native_judge_requires_exact_sse_flags_and_response_metadata(self):
        self.fixture.all_writers()
        folder = self.fixture.attempt("judges", next(iter(self.fixture.judges)))
        self.fixture.change_record(folder, "actual_input_match", 1)
        value = full.read_json(folder / "response.json")
        value["info"]["variant"] = "low"
        value["info"]["providerMetadata"] = {"secret": SECRET}
        save(folder / "response.json", value)
        self.fixture.rehash(folder)
        report = self.audit()
        checks = self.trial(report, folder)["checks"]
        self.assertFalse(checks["native_user_input_audit"])
        self.assertFalse(checks["actual_metadata_matches"])
        self.assertFalse(checks["sanitized_native_response"])
        self.assertNotIn(SECRET, json.dumps(report))

    def test_export_detects_wrong_exact_text_model_variant_and_continuation(self):
        folder = self.fixture.attempt("writers", next(iter(self.fixture.writers)))
        sid = next(iter(self.fixture.exports))
        value = self.fixture.exports[sid]
        value["info"]["parentID"] = "ses_parent"
        value["messages"][0]["parts"][0]["text"] = "Requoted prompt"
        value["messages"][1]["info"].update(modelID="wrong", variant="low")
        value["messages"].insert(0, deepcopy(value["messages"][0]))
        report = self.audit()
        checks = self.trial(report, folder)["exports"][0]["checks"]
        for name in (
            "export_not_forked",
            "export_fresh_exchange",
            "actual_user_input_matches",
            "actual_metadata_matches",
            "exposed_variants_match",
        ):
            self.assertFalse(checks[name])
        self.assertNotIn(SECRET, json.dumps(report))

    def test_unique_sessions_include_failed_retries_and_judges(self):
        self.fixture.all_writers()
        ids = list(self.fixture.judges)
        first = self.fixture.attempt(
            "judges",
            ids[0],
            status="failed",
            kind="schema_or_evidence",
            sid="ses_duplicate",
            value={"bad": True},
        )
        second = self.fixture.attempt("judges", ids[0], 2, sid="ses_duplicate")
        third = self.fixture.attempt(
            "judges", ids[1], sid=next(iter(self.fixture.exports))
        )
        report = self.audit()
        self.assertEqual(report["counts"]["duplicate_sessions"], 2)
        for folder in (first, second, third):
            self.assertFalse(
                self.trial(report, folder)["checks"][
                    "globally_unique_transport_session"
                ]
            )

    def test_corrupt_outcome_does_not_hide_session_or_stop_other_attempts(self):
        ids = list(self.fixture.writers)
        folder = self.fixture.attempt("writers", ids[0])
        self.fixture.attempt("writers", ids[1])
        (folder / "outcome.json").write_bytes(b'{"status":')
        report = self.audit()
        self.assertFalse(report["passed"])
        self.assertEqual(report["counts"]["attempts"], 2)
        self.assertEqual(report["counts"]["sessions"], 2)
        self.assertEqual(report["counts"]["writer_exports"], 2)

    def test_malformed_native_and_response_shapes_preserve_session_accounting(self):
        self.fixture.all_writers()
        folder = self.fixture.attempt("judges", next(iter(self.fixture.judges)))
        save(folder / "native-result.json", [])
        response = full.read_json(folder / "response.json")
        response["parts"] = None
        save(folder / "response.json", response)
        self.fixture.rehash(folder)
        report = self.audit()
        self.assertFalse(report["passed"])
        self.assertEqual(report["counts"]["sessions"], len(self.fixture.writers) + 1)
        self.assertEqual(report["counts"]["writer_exports"], len(self.fixture.writers))
        trial = self.trial(report, folder)
        self.assertIn("native_read:ValueError", trial["errors"])
        self.assertFalse(trial["checks"]["response_parts_shape"])
        self.assertTrue(trial["checks"]["native_user_input_audit"])

    def test_ongoing_native_sessions_are_counted_but_not_exported(self):
        folder = self.fixture.attempt("writers", next(iter(self.fixture.writers)))
        (folder / "outcome.json").unlink()
        report = self.audit()
        self.assertTrue(report["integrity"]["known_checks_passed"])
        self.assertIsNone(report["passed"])
        self.assertFalse(report["complete"])
        self.assertEqual(report["counts"]["sessions"], 1)
        self.assertEqual(report["counts"]["ongoing_sessions"], 1)
        self.assertEqual(report["counts"]["unverified_transport_attempts"], 1)
        self.assertEqual(report["counts"]["writer_exports"], 0)

    def test_artifacts_changed_during_export_fail_the_final_snapshot_check(self):
        folder = self.fixture.attempt("writers", next(iter(self.fixture.writers)))

        def change_output(*args):
            result = self.execute(*args)
            (folder / "output.md").write_bytes(b"Changed during export")
            return result

        self.mock(audit.calibration.run, "execute", side_effect=change_output)
        report = self.audit()
        self.assertFalse(report["passed"])
        self.assertFalse(
            self.trial(report, folder)["checks"]["artifact_hash_output.md"]
        )

    def test_pretransport_failures_and_blocked_jobs_have_explicit_coverage(self):
        for ident in self.fixture.writers:
            folder = self.fixture.start("writers", ident)
            full.finalize_attempt(
                folder,
                {},
                "failed",
                "local_failure",
                ["Synthetic startup failure"],
                0.1,
            )
        report = self.audit()
        self.assertTrue(report["integrity"]["known_checks_passed"])
        self.assertIsNone(report["passed"])
        self.assertTrue(report["complete"])
        self.assertEqual(report["counts"]["failed"], len(self.fixture.writers))
        self.assertEqual(report["counts"]["blocked"], len(self.fixture.judges))
        self.assertEqual(
            report["counts"]["no_observed_session_attempts"], len(self.fixture.writers)
        )
        self.assertEqual(report["counts"]["sessions"], 0)

    def test_interrupted_recovery_records_do_not_require_finalizer_overlay(self):
        ident = next(iter(self.fixture.writers))
        folder = self.fixture.attempt(
            "writers", ident, status="failed", kind="transport"
        )
        native = full.read_json(folder / "native-result.json")
        save(folder / "result.json", native)
        (folder / "native-result.json").unlink()
        outcome = full.read_json(folder / "outcome.json")
        outcome.update(
            failure_kind="interrupted",
            metrics=full.metrics_only(native),
            wall_seconds=None,
        )
        save(folder / "outcome.json", outcome)
        (folder / "checks.json").unlink()
        self.fixture.rehash(folder)
        report = self.audit()
        self.assert_passed(report)
        self.assertEqual(report["counts"]["retry_pending"], 1)
        self.assertEqual(report["counts"]["writer_exports"], 1)

    def test_unknown_jobs_are_reported_and_sessions_remain_in_uniqueness_check(self):
        ids = list(self.fixture.writers)
        folder = self.fixture.attempt("writers", ids[0], sid="ses_duplicate")
        folder.parent.rename(folder.parent.with_name("unknown-job"))
        self.fixture.attempt("writers", ids[1], sid="ses_duplicate")
        report = self.audit()
        self.assertFalse(report["passed"])
        self.assertFalse(report["complete"])
        self.assertEqual(report["counts"]["attempts"], 2)
        self.assertEqual(report["counts"]["duplicate_sessions"], 1)
        unknown = next(t for t in report["attempts"] if t["job"] == "unknown-job")
        self.assertFalse(unknown["checks"]["planned_assignment"])

    def test_missing_selected_artifact_and_schema_hash_cannot_be_hidden_by_rehash(self):
        self.fixture.all_writers()
        writer = self.fixture.folder("writers", next(iter(self.fixture.writers)))
        (writer / "checks.json").unlink()
        self.fixture.rehash(writer)
        judge = self.fixture.attempt("judges", next(iter(self.fixture.judges)))
        for name in ("native-result.json", "result.json"):
            value = full.read_json(judge / name)
            del value["schema_sha256"]
            save(judge / name, value)
        self.fixture.rehash(judge)
        report = self.audit()
        self.assertFalse(report["passed"])
        self.assertFalse(
            self.trial(report, writer)["checks"]["selected_artifact_coverage"]
        )
        self.assertIn("assignment:KeyError", self.trial(report, judge)["errors"])
        self.assertTrue(self.trial(report, judge)["checks"]["native_user_input_audit"])

    def test_retry_after_valid_and_out_of_bound_attempts_are_included(self):
        ident = next(iter(self.fixture.writers))
        self.fixture.attempt("writers", ident)
        second = self.fixture.attempt("writers", ident, 2)
        third = self.fixture.attempt("writers", ident, 3)
        report = self.audit()
        self.assertEqual(report["counts"]["writer_exports"], 3)
        self.assertFalse(
            self.trial(report, second)["checks"]["retry_after_retryable_failure"]
        )
        self.assertFalse(self.trial(report, third)["checks"]["retry_bound"])

    def test_export_errors_are_metadata_only_and_other_exports_continue(self):
        self.fixture.all_writers()
        original = self.execute
        first = next(iter(self.fixture.exports))

        def fail_one(args, *rest):
            if args[2] == first:
                raise ValueError(SECRET)
            return original(args, *rest)

        self.mock(audit.calibration.run, "execute", side_effect=fail_one)
        report = self.audit()
        self.assertIsNone(report["passed"])
        self.assertEqual(report["counts"]["integrity_failed_attempts"], 0)
        self.assertEqual(report["counts"]["integrity_unknown_attempts"], 1)
        self.assertEqual(len(self.executions), len(self.fixture.writers) - 1)
        self.assertNotIn(SECRET, json.dumps(report))

    def test_recovery_verifies_archived_writers_original_invocations_and_new_model(
        self,
    ):
        self.fixture.all_writers()
        original = self.fixture
        self.fixture = original.recovery(self.root / "recovery")
        for ident in self.fixture.judges:
            self.fixture.attempt("judges", ident)
        report = self.audit(check_live_sources=True, source_root=self.root)
        self.assert_passed(report)
        self.assertTrue(report["complete"])
        self.assertTrue(all(report["recovery"]["checks"].values()))
        writers = [t for t in report["attempts"] if t["role"] == "writers"]
        self.assertTrue(
            all(
                t["origin_manifest_sha256"] == original.frozen["manifest_sha256"]
                for t in writers
            )
        )
        self.assertTrue(all(t["reused_writer"] for t in writers))
        self.assertEqual(report["counts"]["writer_exports"], len(original.writers))
        self.assertEqual(
            audit.writer_archive_hashes(original.root),
            audit.writer_archive_hashes(self.fixture.root),
        )

    def test_recovery_tampered_source_copy_or_proof_fails_even_after_rehash(self):
        self.fixture.all_writers()
        original = self.fixture
        self.fixture = original.recovery(self.root / "recovery")
        ident = next(iter(original.writers))
        for target, expected in (
            (original.folder("writers", ident), "source_writer_archive"),
            (self.fixture.folder("writers", ident), "copied_writer_archive"),
        ):
            with self.subTest(check=expected):
                saved = {p: p.read_bytes() for p in target.iterdir() if p.is_file()}
                (target / "output.md").write_bytes(b"Tampered writer")
                self.fixture.rehash(target)
                report = self.audit()
                self.assertIs(report["passed"], False)
                self.assertFalse(report["recovery"]["checks"][expected])
                for path, data in saved.items():
                    path.write_bytes(data)
        provenance = self.fixture.frozen["recovery"]
        provenance["writer_artifact_sha256"].pop(
            next(iter(provenance["writer_artifact_sha256"]))
        )
        self.fixture.save_manifest()
        self.fixture.update_preflight()
        report = self.audit()
        self.assertFalse(report["recovery"]["checks"]["source_writer_archive"])
        self.assertFalse(report["recovery"]["checks"]["copied_writer_archive"])

    def test_recovery_requires_exact_source_manifest_file_and_live_script_hash(self):
        self.fixture.all_writers()
        original = self.fixture
        self.fixture = original.recovery(self.root / "recovery")
        path = original.root / "manifest.json"
        raw = path.read_bytes()
        path.write_bytes(raw + b"\n")
        report = self.audit()
        self.assertFalse(report["recovery"]["checks"]["source_manifest_identity"])
        path.write_bytes(raw)
        (self.root / "evals/documenting/rejudge.py").write_bytes(b"# Changed script\n")
        report = self.audit(check_live_sources=True, source_root=self.root)
        self.assertFalse(report["recovery"]["checks"]["recovery_script_hash"])

    def test_relabeling_copied_writers_without_recovery_provenance_fails(self):
        self.fixture.all_writers()
        self.fixture = self.fixture.recovery(self.root / "recovery")
        del self.fixture.frozen["recovery"]
        self.fixture.save_manifest()
        self.fixture.update_preflight()
        report = self.audit()
        self.assertTrue(report["checks"]["manifest_configuration"])
        self.assertTrue(report["checks"]["judge_preflight_agent"])
        self.assertIs(report["passed"], False)
        self.assertEqual(
            report["counts"]["integrity_failed_attempts"], len(self.fixture.writers)
        )
        self.assertTrue(
            all(not t["checks"]["started_marker"] for t in report["attempts"])
        )

    def test_recovery_cannot_change_writer_settings_or_preflight_model(self):
        self.fixture.all_writers()
        self.fixture = self.fixture.recovery(self.root / "recovery")
        path = self.fixture.root / "preflights/synthetic/preflight-judge-agent.txt"
        agent = full.read_json(path)
        agent["model"]["modelID"] = "wrong"
        save(path, agent)
        report = self.audit()
        self.assertFalse(report["checks"]["judge_preflight_agent"])
        self.fixture.update_preflight()
        self.fixture.frozen["inputs"]["systems"]["C"] += " Changed guidance"
        self.fixture.save_manifest()
        self.fixture.update_preflight()
        report = self.audit()
        self.assertFalse(report["recovery"]["checks"]["unchanged_frozen_study"])

    def test_recovery_rejects_additional_writers_and_tampered_source_selection(self):
        self.fixture.all_writers()
        self.fixture = self.fixture.recovery(self.root / "recovery")
        ident = next(iter(self.fixture.writers))
        self.fixture.attempt("writers", ident, 2)
        report = self.audit()
        self.assertFalse(report["recovery"]["checks"]["copied_writer_archive"])
        self.fixture.frozen["recovery"]["selected_writer_attempts"][ident] = 2
        self.fixture.save_manifest()
        self.fixture.update_preflight()
        report = self.audit()
        self.assertFalse(report["recovery"]["checks"]["source_writer_selection"])

    def test_interrupted_judge_with_only_input_artifacts_is_unknown_not_verified(self):
        self.fixture.all_writers()
        self.fixture = self.fixture.recovery(self.root / "recovery")
        ident = next(iter(self.fixture.judges))
        folder = self.fixture.attempt(
            "judges", ident, status="failed", kind="interrupted"
        )
        for path in folder.iterdir():
            if path.name not in (
                "input.md",
                "system.md",
                "config.json",
                "schema.json",
                "outcome.json",
            ):
                path.unlink()
        outcome = full.read_json(folder / "outcome.json")
        outcome.update(metrics={}, wall_seconds=None)
        save(folder / "outcome.json", outcome)
        self.fixture.rehash(folder)
        self.fixture.attempt("judges", ident, 2)
        for other in self.fixture.judges:
            if other != ident:
                self.fixture.attempt("judges", other)
        report = self.audit()
        self.assertIsNone(report["passed"])
        self.assertTrue(report["complete"])
        self.assertTrue(report["integrity"]["known_checks_passed"])
        trial = self.trial(report, folder)
        self.assertEqual(trial["integrity_status"], "unknown")
        self.assertEqual(trial["session_integrity"], "unknown")
        self.assertNotIn("native_user_input_audit", trial["checks"])
        self.assertEqual(report["counts"]["unknown_session_attempts"], 1)
        self.assertEqual(
            report["counts"]["verified_session_attempts"], report["counts"]["planned"]
        )
        with redirect_stdout(io.StringIO()):
            self.assertEqual(audit.main(["--output", str(self.fixture.root)]), 3)

    def test_unfinished_native_audit_flags_are_unknown_but_explicit_mismatch_fails(
        self,
    ):
        self.fixture.all_writers()
        folder = self.fixture.attempt(
            "judges",
            next(iter(self.fixture.judges)),
            status="failed",
            kind="transport",
            protocol_failure=True,
        )
        self.fixture.change_record(folder, "actual_input_match", False)
        self.fixture.change_record(folder, "session_isolated", False)
        report = self.audit()
        self.assertTrue(report["integrity"]["known_checks_passed"])
        self.assertIsNone(report["passed"])
        self.assertEqual(self.trial(report, folder)["session_integrity"], "unknown")
        for name in ("native-result.json", "result.json", "outcome.json"):
            value = full.read_json(folder / name)
            value["failures"] = ["Session input audit mismatch"]
            save(folder / name, value)
        self.fixture.rehash(folder)
        report = self.audit()
        self.assertIs(report["passed"], False)
        self.assertFalse(
            self.trial(report, folder)["checks"]["native_user_input_audit"]
        )

    def test_previous_report_is_archived_but_does_not_determine_new_verdict(self):
        self.fixture.all_jobs()
        previous = {
            "passed": False,
            "counts": {"integrity_failed_attempts": 999},
            "errors": ["manifest_configuration"],
            "attempts": [{"errors": ["started_marker", "marker:FileNotFoundError"]}],
        }
        save(self.fixture.root / "audit.json", previous)
        raw = (self.fixture.root / "audit.json").read_bytes()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(audit.main(["--output", str(self.fixture.root)]), 0)
        report = full.read_json(self.fixture.root / "audit.json")
        self.assert_passed(report)
        provenance = report["previous_audit"]
        self.assertEqual((self.fixture.root / provenance["artifact"]).read_bytes(), raw)
        self.assertEqual(provenance["attempt_error_counts"]["started_marker"], 1)
        self.assertNotIn("counts", provenance)

    def test_cli_writes_only_report_stdout_counts_and_exit_codes(self):
        capture = io.StringIO()
        with redirect_stdout(capture):
            code = audit.main(["--output", str(self.fixture.root)])
        self.assertEqual(code, 2)
        counts = json.loads(capture.getvalue())
        self.assertTrue(all(type(value) is int for value in counts.values()))
        self.assertEqual(
            counts, full.read_json(self.fixture.root / "audit.json")["counts"]
        )
        self.fixture.all_jobs()
        before = {
            p: p.read_bytes()
            for p in self.fixture.root.rglob("*")
            if p.is_file() and p.name != "audit.json"
        }
        capture = io.StringIO()
        with redirect_stdout(capture):
            code = audit.main(["--output", str(self.fixture.root), "--workers", "2"])
        self.assertEqual(code, 0)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)
        after = {p for p in self.fixture.root.rglob("*") if p.is_file()}
        previous = full.read_json(self.fixture.root / "audit.json")["previous_audit"]
        archive = self.fixture.root / previous["artifact"]
        self.assertEqual(full.file_hash(archive), previous["sha256"])
        self.assertEqual(
            after, set(before) | {self.fixture.root / "audit.json", archive}
        )
        self.assertNotIn(SECRET, audit.text(self.fixture.root / "audit.json"))
        (self.fixture.root / "manifest.json").write_bytes(b"Invalid JSON")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(audit.main(["--output", str(self.fixture.root)]), 1)


if __name__ == "__main__":
    unittest.main()
