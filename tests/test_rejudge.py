"""Offline recovery tests: immutable sources, truthful model routing, no inference."""

from contextlib import ExitStack, redirect_stderr, redirect_stdout
from copy import deepcopy
import fcntl
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


sys.dont_write_bytecode = True
# full.py registers a private runtime package; do not disturb other test imports.
with patch.dict(sys.modules):
    from evals.documenting import rejudge

full, controls = rejudge.full, rejudge.controls
MODEL = "openai/gpt-5.6-luna"


def snapshot(root):
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class RejudgeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="rejudge-offline-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source, self.output = self.root / "source", self.root / "new"
        self.original_model = full.base.JUDGE_MODEL
        self.original_control_model = controls.run.JUDGE_MODEL
        self.original_factory = full.make_manifest
        self.inputs = {}
        self.mock(full, "load_inputs", side_effect=lambda: deepcopy(self.inputs))
        self.preflight = self.mock(
            full.base, "preflight", side_effect=self.preflight_stub
        )
        self.writer = self.mock(
            full.base, "call_model", side_effect=AssertionError("writer call")
        )
        self.adapter = self.mock(
            controls.structured,
            "call_structured",
            side_effect=AssertionError("judge call"),
        )
        self.mock(
            full, "structured", new=types.SimpleNamespace(call_structured=self.adapter)
        )
        for target, name in (
            (full.base, "isolated_runtime"),
            (controls.run, "isolated_runtime"),
            (full.base.subprocess, "Popen"),
            (full.base.subprocess, "check_output"),
            (socket, "socket"),
            (socket, "create_connection"),
        ):
            self.mock(
                target, name, side_effect=AssertionError("Offline boundary: " + name)
            )
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(redirect_stdout(io.StringIO()))
        stack.enter_context(redirect_stderr(io.StringIO()))

    def mock(self, target, name, **kwargs):
        guard = patch.object(target, name, **kwargs)
        result = guard.start()
        self.addCleanup(guard.stop)
        return result

    def preflight_stub(self, folder, frozen):
        self.assertEqual(frozen["judge_model"], full.base.JUDGE_MODEL)
        if "recovery" in frozen:
            self.assertEqual(
                rejudge.writer_hashes(self.output),
                frozen["recovery"]["writer_artifact_sha256"],
            )
            self.assertFalse((self.output / "ready.json").exists())
        full.save_new(
            folder / "preflight.json",
            {
                "version": full.base.VERSION,
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
                        ("writer", full.base.WRITER_MODEL),
                        ("judge", full.base.JUDGE_MODEL),
                    )
                },
            },
        )

    def fixture(self, count=2):
        cases = [
            {
                "id": "synthetic-" + str(i),
                "family": "synthetic",
                "category": full.CATEGORIES[i // 6],
                "split": "development"
                if i % 6 < (2 if count == 36 else 1)
                else "holdout",
                "task": "Revise.",
                "source_facts": "Keep café.",
                "draft": "café\r\n",
                "requirements": [{"id": "r1", "text": "Keep café."}],
                "issues": [],
                "checks": [],
            }
            for i in range(count)
        ]
        self.inputs = {
            "cases": cases,
            "case_metadata": {
                c["id"]: {
                    "category": c["category"],
                    "split": c["split"],
                    "source": "synthetic.json",
                    "source_sha256": full.json_hash(c),
                    "embedded_sha256": full.json_hash(c),
                }
                for c in cases
            },
            "systems": {arm: "Instructions " + arm + " café\r\n" for arm in full.ARMS},
            "judge_system": "Compare.",
            "judge_schemas": {c["id"]: {"type": "object"} for c in cases},
            "source_hashes": {"synthetic.py": "frozen"},
        }
        frozen = full.make_manifest(self.inputs, seed=71, timeout=47)
        self.source.mkdir()
        (self.source / ".execution.lock").touch()
        full.save_new(self.source / "manifest.json", frozen)
        folder = self.source / "preflights/original"
        folder.mkdir(parents=True)
        self.preflight_stub(folder, frozen)
        full.save_new(
            self.source / "ready.json",
            {
                "manifest_sha256": frozen["manifest_sha256"],
                "preflight": "preflights/original/preflight.json",
                "preflight_sha256": full.file_hash(folder / "preflight.json"),
            },
        )
        by_id = {c["id"]: c for c in cases}
        for i, job in enumerate(frozen["jobs"]["writers"]):
            for number in range(1, 3 if i == 0 else 2):
                folder = (
                    self.source / "writers" / job["id"] / ("attempt-" + str(number))
                )
                folder.mkdir(parents=True)
                full.save_new(
                    folder.with_name(folder.name + ".started.json"),
                    {
                        "attempt": number,
                        "manifest_sha256": frozen["manifest_sha256"],
                        "invocation": "original-writers",
                    },
                )
                for name, text in {
                    "system.md": self.inputs["systems"][job["arm"]],
                    "input.md": full.base.writer_prompt(by_id[job["case"]]),
                    "output.md": "café retained\r\n",
                }.items():
                    (folder / name).write_bytes(text.encode("utf-8"))
                failed = i == 0 and number == 1
                result = {
                    "status": "failed" if failed else "completed",
                    "failures": [],
                    "model": frozen["writer_model"],
                    "variant": "high",
                    "session_ids": ["ses_original_" + str(i) + "_" + str(number)],
                    "observed_model_steps": 1,
                }
                full.save_new(folder / "result.json", result)
                full.finalize_attempt(
                    folder,
                    result,
                    "failed" if failed else "valid",
                    "transport" if failed else None,
                    [],
                    1.0,
                )
        for job, status in zip(frozen["jobs"]["judges"][:2], ("failed", "valid")):
            folder = self.source / "judges" / job["id"] / "attempt-1"
            folder.mkdir(parents=True)
            full.save_new(
                folder / "outcome.json", {"status": status, "artifact_sha256": {}}
            )
            (folder / "response.json").write_bytes(b'{"original_judge":"HTTP 402"}\n')
        return frozen

    def init(self):
        return rejudge.initialize(self.source, self.output, MODEL)

    def test_full_reuse_freeze_hashes_provenance_and_no_new_writer_calls(self):
        original = self.fixture(36)
        before = snapshot(self.source)
        self.output.mkdir()  # An existing empty destination is supported.
        self.assertEqual(
            rejudge.main(
                [
                    "init",
                    "--source",
                    str(self.source),
                    "--output",
                    str(self.output),
                    "--judge-model",
                    MODEL,
                ]
            ),
            0,
        )
        frozen = full.load_frozen(self.output)
        full.require_ready(self.output, frozen)
        for field in (
            "inputs",
            "jobs",
            "analysis_plan",
            "policy",
            "seed",
            "timeout",
            "max_attempts",
        ):
            self.assertEqual(frozen[field], original[field])
        self.assertEqual(
            (frozen["judge_model"], frozen["judge_variant"]), (MODEL, "high")
        )
        recovery = frozen["recovery"]
        self.assertEqual(
            recovery["source_manifest_sha256"], original["manifest_sha256"]
        )
        self.assertEqual(
            recovery["source_manifest_file_sha256"],
            full.file_hash(self.source / "manifest.json"),
        )
        self.assertEqual(
            recovery["script_sha256"], full.file_hash(Path(rejudge.__file__))
        )
        self.assertEqual(
            (
                recovery["writer_jobs"],
                recovery["writer_attempts"],
                recovery["fresh_judge_jobs"],
            ),
            (324, 325, 270),
        )
        self.assertEqual(
            (recovery["new_writer_calls"], recovery["reused_judge_attempts"]), (0, 0)
        )
        self.assertEqual(recovery["fresh_judge_splits"], ["development", "holdout"])
        self.assertEqual(
            recovery["writer_artifact_sha256"], rejudge.writer_hashes(self.output)
        )
        self.assertEqual(
            snapshot(self.output / "writers"), snapshot(self.source / "writers")
        )
        index = full.build_index(self.output, frozen, verify=True)
        self.assertEqual(
            index["jobs"]["writers"], rejudge.verified_writers(self.source, original)
        )
        self.assertTrue(
            all(
                not entry["attempts"] and entry["ready"]
                for entry in index["jobs"]["judges"].values()
            )
        )
        counts = full.read_json(self.output / "status.json")["counts"]["all"]
        self.assertEqual(counts["writers"]["valid"], 324)
        self.assertEqual(
            (counts["judges"]["planned"], counts["judges"]["attempted"]), (270, 0)
        )
        self.assertFalse((self.output / "invocations").exists())
        self.assertFalse((self.output / "judges").exists())
        full.run_jobs(self.output, frozen, "writers", split="all")
        self.writer.assert_not_called()
        self.adapter.assert_not_called()
        self.preflight.assert_called_once()
        self.assertEqual(full.base.JUDGE_MODEL, self.original_model)
        self.assertIs(full.make_manifest, self.original_factory)
        self.assertEqual(snapshot(self.source), before)

    def test_native_future_judges_use_frozen_model_and_copies_are_independent(self):
        self.fixture()
        before = snapshot(self.source)
        self.init()
        frozen = full.load_frozen(self.output)

        def fake(folder, *args, **kwargs):
            folder.mkdir(parents=True)
            return {"status": "failed", "failures": ["offline"]}, None

        self.adapter.side_effect = fake
        full.run_jobs(self.output, frozen, "judges", limit=1, concurrency=1)
        self.assertEqual(
            self.adapter.call_count, 2
        )  # One job, its two bounded attempts.
        for call in self.adapter.call_args_list:
            self.assertEqual(
                call.kwargs, {"model": MODEL, "variant": "high", "timeout": 47}
            )
        relative = next(
            p for p in before if p.startswith("writers/") and p.endswith("output.md")
        )
        self.assertFalse((self.output / "writers").is_symlink())
        (self.output / relative).write_bytes(b"independent copy")
        self.assertEqual(snapshot(self.source), before)

    def test_missing_writer_and_tampered_artifacts_rejected_without_output(self):
        original = self.fixture()
        job = original["jobs"]["writers"][0]
        folder = self.source / "writers" / job["id"] / "attempt-2"
        for name in ("outcome.json", "output.md"):
            path = folder / name
            retained = path.read_bytes()
            if name == "outcome.json":
                path.unlink()
            else:
                path.write_bytes(b"tampered")
            before = snapshot(self.source)
            with self.assertRaises(ValueError):
                self.init()
            self.assertEqual(snapshot(self.source), before)
            self.assertFalse(self.output.exists())
            path.write_bytes(retained)
        # Verify failed attempts too, rather than checking only selected outputs.
        (folder.parent / "attempt-1/output.md").write_bytes(b"tampered failed attempt")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            self.init()
        self.preflight.assert_not_called()
        self.writer.assert_not_called()

    def test_changed_freeze_inputs_and_nonempty_or_overlapping_output_are_rejected(
        self,
    ):
        self.fixture()
        self.inputs["source_hashes"]["synthetic.py"] = "changed"
        with self.assertRaisesRegex(ValueError, "Frozen sources"):
            self.init()
        self.inputs["source_hashes"]["synthetic.py"] = "frozen"
        before = snapshot(self.source)
        self.output.mkdir()
        (self.output / "failure.json").write_bytes(b"keep failed run")
        failed = snapshot(self.output)
        for output in (self.output, self.source, self.source / "nested"):
            with self.assertRaises(ValueError):
                rejudge.initialize(self.source, output, MODEL)
        self.assertEqual(snapshot(self.output), failed)
        self.assertEqual(snapshot(self.source), before)
        self.preflight.assert_not_called()

    def test_preflight_failure_preserves_source_and_never_publishes_ready(self):
        self.fixture()
        before = snapshot(self.source)
        self.preflight.side_effect = ValueError("synthetic preflight failure")
        with self.assertRaisesRegex(ValueError, "preflight failure"):
            self.init()
        self.assertFalse((self.output / "ready.json").exists())
        frozen = full.load_frozen(self.output)
        self.assertEqual(frozen["judge_model"], MODEL)
        self.assertEqual(full.base.JUDGE_MODEL, self.original_model)
        self.assertIs(full.make_manifest, self.original_factory)
        self.assertEqual(snapshot(self.source), before)
        failed = snapshot(self.output)
        with self.assertRaisesRegex(ValueError, "empty output"):
            self.init()
        self.assertEqual(snapshot(self.output), failed)

    def test_busy_source_and_linked_writer_artifacts_are_rejected(self):
        frozen = self.fixture()
        with (self.source / ".execution.lock").open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(full.OutputBusy):
                self.init()
        job = frozen["jobs"]["writers"][0]
        path = self.source / "writers" / job["id"] / "attempt-1/output.md"
        path.unlink()
        path.symlink_to(self.source / "manifest.json")
        with self.assertRaisesRegex(ValueError, "artifact path"):
            self.init()
        self.assertFalse(self.output.exists())

    def test_controls_route_all_twelve_calls_and_retain_failures_without_retry(self):
        baseline = controls.build_manifest()

        def fake(folder, system, prompt, schema, **settings):
            self.assertEqual(
                settings, {"model": MODEL, "variant": "high", "timeout": 600}
            )
            self.assertEqual(controls.run.JUDGE_MODEL, self.original_control_model)
            job = next(j for j in baseline["jobs"] if j["id"] == folder.parent.name)
            control = next(c for c in baseline["controls"] if c["id"] == job["control"])
            self.assertEqual(json.loads(prompt), controls.inputs(control, job["order"]))
            self.assertEqual((system, schema), (baseline["system"], control["schema"]))
            folder.mkdir()
            native = {
                "status": "failed",
                "failures": ["synthetic HTTP 402"],
                **settings,
            }
            controls.save(folder / "result.json", native)
            return native, None

        self.adapter.side_effect = fake
        with patch.object(
            controls, "ThreadPoolExecutor", wraps=controls.ThreadPoolExecutor
        ) as pool:
            self.assertEqual(
                rejudge.main(
                    [
                        "controls",
                        "--output",
                        str(self.output),
                        "--judge-model",
                        MODEL,
                        "--concurrency",
                        "3",
                    ]
                ),
                1,
            )
            pool.assert_called_once_with(max_workers=3)
        self.assertEqual(self.adapter.call_count, 12)
        self.assertEqual(
            len({call.args[0] for call in self.adapter.call_args_list}), 12
        )
        # trial catches transport exceptions, including assertions in the stub.
        # Require its native records so a routing assertion cannot pass silently.
        for call in self.adapter.call_args_list:
            native = full.read_json(call.args[0] / "result.json")
            self.assertEqual((native["model"], native["variant"]), (MODEL, "high"))
        saved = full.read_json(self.output / "manifest.json")
        manifest = saved["manifest"]
        self.assertEqual(saved["sha256"], controls.fingerprint(manifest))
        self.assertEqual(manifest["model"], MODEL)
        self.assertEqual(manifest["recovery"]["new_writer_calls"], 0)
        for key in (
            "controls",
            "jobs",
            "system",
            "source_hashes",
            "variant",
            "timeout",
        ):
            self.assertEqual(manifest[key], baseline[key])
        self.assertEqual(
            full.read_json(self.output / "summary.json")["counts"]["transport_error"],
            12,
        )
        before = snapshot(self.output)
        with self.assertRaisesRegex(ValueError, "new output"):
            rejudge.run_controls(self.output, MODEL)
        self.assertEqual(snapshot(self.output), before)
        self.assertEqual(self.adapter.call_count, 12)
        self.preflight.assert_not_called()
        self.writer.assert_not_called()

    def test_controls_validate_before_creating_output_or_initializing(self):
        self.mock(controls, "build_manifest", side_effect=ValueError("invalid control"))
        initialize = self.mock(
            full, "initialize", side_effect=AssertionError("init before controls")
        )
        with self.assertRaisesRegex(ValueError, "invalid control"):
            rejudge.run_controls(self.output, MODEL)
        self.assertEqual(controls.run.JUDGE_MODEL, self.original_control_model)
        self.assertFalse(self.output.exists())
        initialize.assert_not_called()
        self.adapter.assert_not_called()
        for model in ("invalid", "openai/", full.base.WRITER_MODEL):
            with self.assertRaises(ValueError):
                rejudge.run_controls(self.output, model)
        with self.assertRaises(ValueError):
            rejudge.run_controls(self.output, MODEL, concurrency=0)


if __name__ == "__main__":
    unittest.main()
