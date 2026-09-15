"""Offline full-suite orchestration tests; real case contents are never displayed."""

from collections import Counter
from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evals/documenting/full.py"
SPEC = importlib.util.spec_from_file_location("full_under_test", SOURCE)
assert SPEC is not None and SPEC.loader is not None
full = importlib.util.module_from_spec(SPEC)
# Each driver import registers the same private package. Keep this test module's
# instance without replacing registrations owned by other test modules.
with patch.dict(sys.modules):
    SPEC.loader.exec_module(full)


def synthetic_case(number=0, category="duplication", split="development"):
    return {
        "id": "identity-sentinel-" + str(number),
        "family": "family-sentinel",
        "category": category,
        "split": split,
        "task": "Revise this document.",
        "source_facts": "The required word is retained.",
        "draft": "retained",
        "requirements": [{"id": "r1", "text": "Keep the required word."}],
        "issues": [{"id": "i1", "text": "Improve the wording if useful."}],
        "checks": [
            {"id": "c1", "requirement": "r1", "kind": "contains", "value": "retained"}
        ],
    }


def synthetic_inputs(small=False):
    if small:
        cases = [synthetic_case(0), synthetic_case(1, split="holdout")]
    else:
        cases = [
            synthetic_case(i * 6 + j, category, "development" if j < 2 else "holdout")
            for i, category in enumerate(full.CATEGORIES)
            for j in range(6)
        ]
    metadata = {
        case["id"]: {
            "category": case["category"],
            "split": case["split"],
            "source": "synthetic/" + case["id"] + ".json",
            "source_sha256": full.json_hash(case),
            "embedded_sha256": full.json_hash(case),
        }
        for case in cases
    }
    return {
        "cases": cases,
        "case_metadata": metadata,
        "systems": {arm: "Frozen writer instructions " + arm for arm in full.ARMS},
        "judge_system": "Frozen synthetic judge instructions",
        "judge_schemas": {
            case["id"]: {
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
                "additionalProperties": False,
            }
            for case in cases
        },
        "source_hashes": {"synthetic-source": "frozen"},
    }


def preflight_checks():
    return {
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
    }


def native_result(status="completed"):
    return {
        "status": status,
        "failures": [] if status == "completed" else ["Synthetic transport failure"],
        "seconds": 2.5,
        "reported_cost": 0.125,
        "observed_model_steps": 1,
        "tokens": dict(zip(full.TOKENS, (100, 10, 20, 30, 40))),
        "session_ids": ["ses_synthetic"],
        "output_words": 1,
    }


class OfflineTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        # Lazy relative imports must see this instance's package and base; restore
        # the registry (including any newly imported adapters) after each test.
        runtime = patch.dict(
            sys.modules,
            {full.PACKAGE: full.package, full.PACKAGE + ".run": full.base},
        )
        runtime.start()
        self.addCleanup(runtime.stop)
        for target, name in (
            (full.base, "isolated_runtime"),
            (full.base, "execute"),
            (full.base.subprocess, "Popen"),
            (full.base.subprocess, "check_output"),
            (socket, "socket"),
            (socket, "create_connection"),
        ):
            self.mock(
                target, name, side_effect=AssertionError("Offline boundary: " + name)
            )
        self.capture = io.StringIO()
        redirect = redirect_stdout(self.capture)
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)

    def mock(self, target, name, **kwargs):
        guard = patch.object(target, name, **kwargs)
        mocked = guard.start()
        self.addCleanup(guard.stop)
        return mocked


class SuiteTests(OfflineTests):
    def test_real_suite_validates_without_exposing_individual_contents(self):
        # Assert aggregate metadata only, even if this test fails.
        cases, metadata = full.load_cases()
        self.assertEqual(len(cases), 36)
        self.assertEqual(
            Counter(item["split"] for item in metadata.values()),
            {"development": 12, "holdout": 24},
        )
        self.assertEqual(self.capture.getvalue(), "")

    def test_strict_suite_count_categories_splits_and_annotation_validation(self):
        inputs = synthetic_inputs()
        cases, metadata = inputs["cases"], inputs["case_metadata"]
        full.validate_suite(cases, metadata)
        with self.assertRaisesRegex(ValueError, "exactly 36"):
            full.validate_suite(cases[:35], metadata)
        with self.assertRaisesRegex(ValueError, "exactly 36"):
            full.validate_suite(cases[:-1] + cases[:1], metadata)
        bad = deepcopy(cases)
        bad[0]["split"] = "holdout"
        bad_meta = deepcopy(metadata)
        bad_meta[bad[0]["id"]]["split"] = "holdout"
        with self.assertRaisesRegex(ValueError, "2 development and 4 holdout"):
            full.validate_suite(bad, bad_meta)
        for mutate in (
            lambda c: c.update(draft=3),
            lambda c: c.update(id="../unsafe"),
            lambda c: c.update(requirements=[]),
            lambda c: c["requirements"].append(deepcopy(c["requirements"][0])),
            lambda c: c["checks"][0].update(requirement="absent"),
            lambda c: c["checks"][0].update(kind="regex", value="["),
            lambda c: c["checks"][0].update(kind="count_at_least", minimum=True),
            lambda c: c.update(draft="No required word"),
        ):
            case = synthetic_case()
            mutate(case)
            with self.assertRaises(ValueError):
                full.validate_case(case)

    def test_schedule_counts_repetitions_pairs_and_stratified_swaps(self):
        inputs = synthetic_inputs()
        jobs = full.make_schedule(inputs["cases"], inputs["case_metadata"], 100)
        self.assertEqual(
            {role: len(items) for role, items in jobs.items()},
            {"writers": 324, "judges": 270},
        )
        self.assertEqual(
            len({job["id"] for job in jobs["writers"] + jobs["judges"]}), 594
        )
        for case in inputs["cases"]:
            actual = Counter(
                (job["arm"], job["repetition"])
                for job in jobs["writers"]
                if job["case"] == case["id"]
            )
            self.assertEqual(
                actual, Counter((arm, rep) for arm in full.ARMS for rep in range(1, 4))
            )
        primaries = {
            job["id"]: job for job in jobs["judges"] if job["kind"] == "primary"
        }
        swaps = [job for job in jobs["judges"] if job["kind"] == "swap"]
        self.assertEqual(len(primaries), 216)
        self.assertEqual(len(swaps), 54)
        self.assertEqual(
            Counter(job["split"] for job in swaps), {"development": 18, "holdout": 36}
        )
        self.assertEqual(
            Counter((job["category"], job["split"]) for job in swaps),
            Counter(
                {
                    (cat, split): count
                    for cat in full.CATEGORIES
                    for split, count in (("development", 3), ("holdout", 6))
                }
            ),
        )
        self.assertEqual(
            Counter(job["pair"] for job in primaries.values()), {"AB": 108, "BC": 108}
        )
        for job in swaps:
            primary = primaries[job["primary_id"]]
            self.assertEqual(
                (job["left"], job["right"]), (primary["right"], primary["left"])
            )
            self.assertEqual(
                (job["left_writer"], job["right_writer"]),
                (primary["right_writer"], primary["left_writer"]),
            )
            self.assertEqual(job["repetition"], primary["repetition"])
        self.assertEqual(
            jobs,
            full.make_schedule(inputs["cases"][::-1], inputs["case_metadata"], 100),
        )
        other = full.make_schedule(inputs["cases"], inputs["case_metadata"], 101)
        self.assertNotEqual(jobs["writers"], other["writers"])
        self.assertNotEqual(jobs["judges"], other["judges"])
        self.assertEqual(
            {job["left"] + job["right"] for job in primaries.values()},
            {"AB", "BA", "BC", "CB"},
        )

    def test_payload_allowlist_has_no_identity_or_routing_metadata(self):
        case = synthetic_case()
        case["extra_private_label"] = "PRIVATE-LABEL"
        writer = full.base.writer_prompt(case)
        payload = full.judge_payload(case, "Left document", "Right document")
        self.assertEqual(
            set(payload),
            {"task", "source_facts", "draft", "requirements", "issues", "candidates"},
        )
        for text in (writer, full.json_text(payload)):
            for value in (
                case["id"],
                case["family"],
                case["split"],
                case["category"],
                "PRIVATE-LABEL",
            ):
                self.assertNotIn(value, text)
        self.assertNotIn("r1", writer)
        self.assertEqual(payload["requirements"], case["requirements"])
        self.assertEqual(
            payload["candidates"], {"left": "Left document", "right": "Right document"}
        )


class SourceTests(OfflineTests):
    def test_zero_filled_transport_metrics_are_unknown_usage(self):
        result = native_result("failed")
        result.update(
            observed_model_steps=0,
            reported_cost=0,
            tokens={key: 0 for key in full.TOKENS},
        )
        usage = full.usage([{"status": "failed", "metrics": full.metrics_only(result)}])
        self.assertEqual(usage["tokens"]["input"]["unknown_attempts"], 1)
        self.assertEqual(usage["reported_cost"]["unknown_attempts"], 1)
        self.assertEqual(usage["usage_observed_attempts"], 0)
        self.assertEqual(usage["seconds"]["sum"], 2.5)

    def test_actual_source_bytes_are_hashed_and_analysis_documents_are_excluded(self):
        temporary = tempfile.TemporaryDirectory(prefix="full-source-offline-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        here = root / "evals/documenting"
        here.mkdir(parents=True)
        prompt = root / "frozen-prompt.md"
        prompt.write_bytes(b"Frozen prompt\r\n")
        for name in ("full.py", "structured.py", "judging.py"):
            (here / name).write_text("# Synthetic runtime source\n")
        inputs = synthetic_inputs()
        judge = types.SimpleNamespace(
            system_prompt=lambda: inputs["judge_system"],
            schema_for=lambda case: inputs["judge_schemas"][case["id"]],
        )
        self.mock(full, "ROOT", new=root)
        self.mock(full, "HERE", new=here)
        self.mock(full, "judging", new=judge)
        self.mock(
            full, "load_cases", return_value=(inputs["cases"], inputs["case_metadata"])
        )
        self.mock(
            full.base,
            "load_inputs",
            return_value={
                "systems": inputs["systems"],
                "source_hashes": {"frozen-prompt.md": "ignored"},
            },
        )
        first = full.load_inputs()
        self.assertEqual(
            first["source_hashes"]["frozen-prompt.md"], full.file_hash(prompt)
        )
        self.assertEqual(first["systems"], inputs["systems"])
        self.assertEqual(
            set(first["source_hashes"]),
            {
                "frozen-prompt.md",
                "evals/documenting/full.py",
                "evals/documenting/structured.py",
                "evals/documenting/judging.py",
            },
        )
        (here / "analysis.md").write_text("Post-analysis edits.")
        (here / "analyze.py").write_text("# Separate analysis implementation\n")
        self.assertEqual(full.load_inputs(), first)
        prompt.write_bytes(b"Frozen prompt\n")
        self.assertNotEqual(full.load_inputs()["source_hashes"], first["source_hashes"])

    def test_native_adapter_import_reuses_the_importlib_loaded_base(self):
        self.mock(full, "structured", new=None)
        self.assertIs(full.structured_module().run, full.base)
        self.assertTrue(sys.dont_write_bytecode)


class ArtifactTests(OfflineTests):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory(prefix="full-eval-offline-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root / "run"
        self.inputs = synthetic_inputs()
        self.mock(full, "load_inputs", side_effect=lambda: deepcopy(self.inputs))
        self.preflight = self.mock(
            full.base, "preflight", side_effect=self.fake_preflight
        )
        self.judge = types.SimpleNamespace(
            validate=Mock(), schema_for=Mock(), system_prompt=Mock()
        )
        self.mock(full, "judging", new=self.judge)
        self.adapter = types.SimpleNamespace(
            call_structured=Mock(side_effect=self.fake_judge)
        )
        self.mock(full, "structured", new=self.adapter)
        self.writer = self.mock(full.base, "call_model", side_effect=self.fake_writer)
        self.mock(
            full.base,
            "initialize",
            side_effect=AssertionError("Calibration initialize called"),
        )

    def fake_preflight(self, folder, frozen):
        self.assertTrue((self.output / "manifest.json").exists())
        self.assertEqual(set(frozen["inputs"]["systems"]), {"A", "B", "C"})
        full.save_new(folder / "preflight.json", preflight_checks())

    def fake_writer(self, folder, system, prompt, model, variant, timeout):
        folder.mkdir(parents=True, exist_ok=False)
        text = "retained"
        (folder / "output.md").write_text(text)
        result = native_result()
        full.save_new(folder / "result.json", result)
        return result, text

    def fake_judge(self, folder, system, prompt, schema, model, variant, timeout):
        folder.mkdir(parents=True, exist_ok=False)
        value = {"ok": True}
        full.save_new(folder / "structured.json", value)
        full.save_new(folder / "response.json", {"native": value})
        result = native_result()
        full.save_new(folder / "result.json", result)
        return result, value

    def initialize_small(self, maximum=2):
        self.inputs = synthetic_inputs(small=True)
        frozen = full.initialize(self.output, max_attempts=maximum)
        # Small orchestration fixtures bypass load_cases, which strictly requires 36.
        frozen["jobs"]["writers"] = [
            job
            for job in frozen["jobs"]["writers"]
            if job["repetition"] == 1 and job["arm"] in ("A", "B")
        ]
        frozen["jobs"]["judges"] = [
            job
            for job in frozen["jobs"]["judges"]
            if job["repetition"] == 1
            and job["pair"] == "AB"
            and job["kind"] == "primary"
        ]
        return frozen

    def test_init_freezes_complete_schedule_and_resume_does_not_repreflight(self):
        frozen = full.initialize(self.output)
        original = (self.output / "manifest.json").read_bytes()
        self.assertEqual(len(frozen["jobs"]["writers"]), 324)
        self.assertEqual(len(frozen["jobs"]["judges"]), 270)
        self.assertEqual(frozen["inputs"]["cases"], self.inputs["cases"])
        self.assertEqual(frozen["writer_variant"], "high")
        self.assertEqual(frozen["judge_variant"], "high")
        self.assertEqual(frozen["max_attempts"], 2)
        full.initialize(self.output)
        self.assertEqual((self.output / "manifest.json").read_bytes(), original)
        self.preflight.assert_called_once()
        self.writer.assert_not_called()
        self.adapter.call_structured.assert_not_called()
        self.assertEqual(
            full.status(self.output, frozen)["counts"]["development"]["judges"][
                "planned"
            ],
            90,
        )

    def test_freeze_rejects_source_case_prompt_and_manifest_changes_but_allows_reports(
        self,
    ):
        frozen = full.initialize(self.output)
        (self.output / "post-analysis.md").write_text("Descriptive notes can change.")
        full.load_frozen(self.output)
        original = deepcopy(self.inputs)
        for mutate in (
            lambda: self.inputs["source_hashes"].update(
                {"synthetic-source": "changed"}
            ),
            lambda: self.inputs["cases"][0].update(task="Changed task"),
            lambda: self.inputs["systems"].update(A="Changed instructions"),
            lambda: self.inputs.update(judge_system="Changed rubric"),
        ):
            mutate()
            with self.assertRaisesRegex(ValueError, "Frozen sources"):
                full.load_frozen(self.output)
            self.inputs = deepcopy(original)
        frozen["seed"] += 1
        full.save_cache(self.output / "manifest.json", frozen)
        with self.assertRaisesRegex(ValueError, "Manifest hash"):
            full.load_frozen(self.output)

    def test_both_high_variants_must_be_present_and_failed_preflight_can_resume(self):
        def bad_preflight(folder, frozen):
            checks = preflight_checks()
            checks["models"]["judge"]["variants"] = {"default": {}}
            full.save_new(folder / "preflight.json", checks)

        self.preflight.side_effect = bad_preflight
        with self.assertRaisesRegex(ValueError, "high variant unavailable: judge"):
            full.initialize(self.output)
        self.assertFalse((self.output / "ready.json").exists())
        original = (self.output / "manifest.json").read_bytes()
        self.preflight.side_effect = self.fake_preflight
        full.initialize(self.output)
        self.assertEqual((self.output / "manifest.json").read_bytes(), original)
        self.assertEqual(len(list((self.output / "preflights").iterdir())), 2)

    def test_split_gating_chunking_resume_and_judge_dependency_mapping(self):
        frozen = self.initialize_small()
        with self.assertRaisesRegex(ValueError, "Development"):
            full.run_jobs(self.output, frozen, "writers", "holdout")
        full.run_jobs(self.output, frozen, "writers", "all", limit=1, concurrency=1)
        self.assertEqual(self.writer.call_count, 1)
        self.assertEqual(
            full.run_jobs(self.output, frozen, "judges")["development"]["judges"][
                "attempted"
            ],
            0,
        )
        full.run_jobs(self.output, frozen, "writers", "all", concurrency=2)
        self.assertEqual(self.writer.call_count, 2)
        full.run_jobs(self.output, frozen, "writers")
        self.assertEqual(self.writer.call_count, 2)
        full.run_jobs(self.output, frozen, "judges", "development", limit=1)
        self.assertEqual(self.adapter.call_structured.call_count, 1)
        self.assertTrue(full.status(self.output, frozen)["development_complete"])
        call = self.adapter.call_structured.call_args
        self.assertEqual(call.kwargs["variant"], "high")
        self.assertEqual(call.kwargs["model"], full.base.JUDGE_MODEL)
        self.assertEqual(
            set(json.loads(call.args[2])),
            {"task", "source_facts", "draft", "requirements", "issues", "candidates"},
        )
        self.assertEqual(
            call.args[3], self.inputs["judge_schemas"][self.inputs["cases"][0]["id"]]
        )
        self.judge.validate.assert_called_once_with(
            {"ok": True}, self.inputs["cases"][0], "retained", "retained"
        )
        mapping = full.read_json(call.args[0] / "mapping.json")
        self.assertEqual(set(mapping["writers"]), {"left", "right"})
        self.assertTrue(
            all(value["attempt"] == 1 for value in mapping["writers"].values())
        )
        full.run_jobs(self.output, frozen, "writers", "holdout")
        full.run_jobs(self.output, frozen, "judges", "holdout")
        self.assertEqual(self.writer.call_count, 4)
        self.assertEqual(self.adapter.call_structured.call_count, 2)
        self.assertEqual(
            full.status(self.output, frozen)["counts"]["holdout"]["judges"]["valid"], 1
        )

    def test_writer_transport_retry_retains_failure_first_attempt_and_usage(self):
        frozen = self.initialize_small()

        def fail_first(folder, *args):
            result, text = self.fake_writer(folder, *args)
            if folder.name == "attempt-1":
                result = native_result("failed")
                full.save_cache(folder / "result.json", result)
            return result, text

        self.writer.side_effect = fail_first
        full.run_jobs(self.output, frozen, "writers", limit=1, concurrency=1)
        self.assertEqual(self.writer.call_count, 2)
        self.assertNotEqual(
            self.writer.call_args_list[0].args[0], self.writer.call_args_list[1].args[0]
        )
        index = full.build_index(self.output, frozen, verify=True)
        entry = next(
            item for item in index["jobs"]["writers"].values() if item["attempts"]
        )
        self.assertEqual(entry["selected_first_valid"], 2)
        self.assertEqual(entry["first_attempt_status"], "failed")
        self.assertEqual(
            [item["status"] for item in entry["attempts"]], ["failed", "valid"]
        )
        first_folder = self.output / entry["attempts"][0]["folder"]
        first_bytes = (first_folder / "result.json").read_bytes()
        full.run_jobs(self.output, frozen, "writers", limit=1)
        self.assertEqual((first_folder / "result.json").read_bytes(), first_bytes)
        summary = full.summarize(self.output, frozen)
        usage = summary["usage"]["development"]["writers"]
        self.assertEqual(usage["first_attempt_validity_rate"], 0)
        self.assertEqual(usage["first_attempt"]["attempts"], 2)
        self.assertEqual(usage["retained_retries"]["attempts"], 2)
        self.assertEqual(usage["all_attempts"]["tokens"]["input"]["sum"], 400)
        self.assertEqual(len(summary["execution"]), 2)
        self.assertTrue(
            all(item["finish"]["wall_seconds"] >= 0 for item in summary["execution"])
        )

    def test_schema_evidence_failure_preserves_native_response_usage_and_retries_once(
        self,
    ):
        frozen = self.initialize_small()
        full.run_jobs(self.output, frozen, "writers")
        self.judge.validate.side_effect = [ValueError("PRIVATE quote not found"), None]
        full.run_jobs(self.output, frozen, "judges")
        self.assertEqual(self.adapter.call_structured.call_count, 2)
        first = self.adapter.call_structured.call_args_list[0].args[0]
        final = full.read_json(first / "result.json")
        self.assertEqual(final["status"], "failed")
        self.assertEqual(final["failure_kind"], "schema_or_evidence")
        self.assertEqual(final["tokens"]["input"], 100)
        self.assertEqual(
            full.read_json(first / "native-result.json")["status"], "completed"
        )
        self.assertEqual(full.read_json(first / "structured.json"), {"ok": True})
        self.assertEqual(
            full.read_json(first / "response.json"), {"native": {"ok": True}}
        )
        self.assertFalse((first / "judgment.json").exists())
        self.assertTrue(
            (self.adapter.call_structured.call_args.args[0] / "judgment.json").exists()
        )
        self.assertNotIn("PRIVATE", self.capture.getvalue())
        self.assertNotIn("PRIVATE", json.dumps(full.summarize(self.output, frozen)))

    def test_semantic_failures_and_uncertainty_never_cause_retries(self):
        frozen = self.initialize_small()

        def lost_requirement(folder, *args):
            result, _ = self.fake_writer(folder, *args)
            (folder / "output.md").write_text("Meaning lost")
            return result, "Meaning lost"

        self.writer.side_effect = lost_requirement
        full.run_jobs(self.output, frozen, "writers")
        self.assertEqual(self.writer.call_count, 2)

        def uncertain(folder, *args, **kwargs):
            result, _ = self.fake_judge(folder, *args, **kwargs)
            value = {"winner": "uncertain", "semantic_status": "fail"}
            full.save_cache(folder / "structured.json", value)
            return result, value

        self.adapter.call_structured.side_effect = uncertain
        full.run_jobs(self.output, frozen, "judges")
        full.run_jobs(self.output, frozen, "judges")
        self.assertEqual(self.adapter.call_structured.call_count, 1)
        index = full.build_index(self.output, frozen)
        self.assertEqual(full.status_counts(index)["development"]["judges"]["valid"], 1)

    def test_exhaustion_blocks_dependent_judges_and_can_finish_development(self):
        frozen = self.initialize_small()

        def fail(folder, *args):
            _, text = self.fake_writer(folder, *args)
            result = native_result("failed")
            full.save_cache(folder / "result.json", result)
            return result, text

        self.writer.side_effect = fail
        full.run_jobs(self.output, frozen, "writers")
        self.assertEqual(self.writer.call_count, 4)
        full.run_jobs(self.output, frozen, "writers")
        self.assertEqual(self.writer.call_count, 4)
        report = full.status(self.output, frozen)
        self.assertTrue(report["development_complete"])
        self.assertEqual(report["counts"]["development"]["judges"]["blocked"], 1)
        full.run_jobs(self.output, frozen, "judges")
        self.adapter.call_structured.assert_not_called()

    def test_crash_recovery_retains_partial_files_and_uses_next_attempt(self):
        frozen = self.initialize_small()
        job = next(
            job for job in frozen["jobs"]["writers"] if job["split"] == "development"
        )
        folder = self.output / "writers" / job["id"] / "attempt-1"
        folder.mkdir(parents=True)
        partial = folder / "output.md"
        partial.write_text("Partial output from interrupted job")
        (folder / "result.json").write_text('{"partial":')
        full.run_jobs(self.output, frozen, "writers", limit=1)
        self.assertEqual(self.writer.call_count, 1)
        self.assertEqual(self.writer.call_args.args[0].name, "attempt-2")
        self.assertEqual(partial.read_text(), "Partial output from interrupted job")
        self.assertEqual((folder / "result.json").read_text(), '{"partial":')
        outcome = full.read_json(folder / "outcome.json")
        self.assertEqual(outcome["failure_kind"], "interrupted")
        self.assertEqual(
            full.summarize(self.output, frozen)["usage"]["development"]["writers"][
                "first_attempt"
            ]["tokens"]["input"]["unknown_attempts"],
            1,
        )

    def test_interrupt_stops_new_jobs_and_records_invocation(self):
        frozen = self.initialize_small()

        def interrupted(folder, *args):
            folder.mkdir(parents=True)
            (folder / "partial.txt").write_text("Keep this")
            raise KeyboardInterrupt

        self.writer.side_effect = interrupted
        with self.assertRaises(KeyboardInterrupt):
            full.run_jobs(self.output, frozen, "writers", concurrency=1)
        self.assertEqual(self.writer.call_count, 1)
        files = list((self.output / "invocations").glob("*.finished.json"))
        self.assertTrue(full.read_json(files[0])["interrupted"])
        self.assertEqual(
            (self.writer.call_args.args[0] / "partial.txt").read_text(), "Keep this"
        )

    def test_concurrency_is_bounded_and_status_is_available_during_execution(self):
        frozen = self.initialize_small()
        gate = threading.Barrier(2, timeout=5)
        active, maximum = 0, 0
        lock = threading.Lock()

        def concurrent(folder, *args):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            gate.wait()
            report = full.status(self.output, frozen)
            self.assertTrue(report["execution_active"])
            result = self.fake_writer(folder, *args)
            with lock:
                active -= 1
            return result

        self.writer.side_effect = concurrent
        full.run_jobs(self.output, frozen, "writers", concurrency=2)
        self.assertEqual(maximum, 2)
        self.assertEqual(
            full.status(self.output, frozen)["counts"]["development"]["writers"][
                "valid"
            ],
            2,
        )

    def test_changed_retained_output_is_rejected_before_judging(self):
        frozen = self.initialize_small()
        full.run_jobs(self.output, frozen, "writers")
        folder = self.writer.call_args.args[0]
        (folder / "output.md").write_text("Changed after selection")
        with self.assertRaisesRegex(ValueError, "Retained attempt artifact changed"):
            full.run_jobs(self.output, frozen, "judges")
        self.adapter.call_structured.assert_not_called()

    def test_metadata_commands_do_not_read_candidate_outputs_or_judgments(self):
        frozen = self.initialize_small()
        full.run_jobs(self.output, frozen, "writers")
        full.run_jobs(self.output, frozen, "judges")
        original = Path.read_bytes

        def guarded(path):
            if path.name in (
                "output.md",
                "judgment.json",
                "structured.json",
                "response.json",
            ):
                raise AssertionError("Metadata command read model text")
            return original(path)

        with patch.object(Path, "read_bytes", guarded):
            full.status(self.output, frozen)
            summary = full.summarize(self.output, frozen)
        self.assertNotIn('"retained"', json.dumps(summary["usage"]))

    def test_transport_exception_retries_in_a_new_folder(self):
        frozen = self.initialize_small()

        def timeout_once(folder, *args):
            if folder.name == "attempt-1":
                raise TimeoutError("PRIVATE transport text")
            return self.fake_writer(folder, *args)

        self.writer.side_effect = timeout_once
        full.run_jobs(self.output, frozen, "writers", limit=1, concurrency=1)
        self.assertEqual(self.writer.call_count, 2)
        self.assertNotIn("PRIVATE", self.capture.getvalue())
        report = full.status(self.output, frozen)
        self.assertEqual(
            report["counts"]["development"]["writers"]["retry_selected"], 1
        )

    def test_local_programming_errors_are_not_retried_on_resume(self):
        frozen = self.initialize_small()
        self.writer.side_effect = RuntimeError("Synthetic local error")
        full.run_jobs(self.output, frozen, "writers")
        full.run_jobs(self.output, frozen, "writers")
        self.assertEqual(self.writer.call_count, 2)
        entries = full.build_index(self.output, frozen)["jobs"]["writers"].values()
        failed = [entry for entry in entries if entry["attempts"]]
        self.assertTrue(
            all(entry["terminal"] and len(entry["attempts"]) == 1 for entry in failed)
        )

    def test_cli_reports_exhausted_failure_and_respects_one_attempt_bound(self):
        full.initialize(self.output, max_attempts=1)

        def fail(folder, *args):
            _, text = self.fake_writer(folder, *args)
            result = native_result("failed")
            full.save_cache(folder / "result.json", result)
            return result, text

        self.writer.side_effect = fail
        self.assertEqual(
            full.main(["writers", "--output", str(self.output), "--limit", "1"]), 1
        )
        self.assertEqual(self.writer.call_count, 1)

    def test_cli_init_status_and_argument_sanitization(self):
        self.assertEqual(full.main(["init", "--output", str(self.output)]), 0)
        self.assertEqual(full.main(["status", "--output", str(self.output)]), 0)
        self.assertEqual(full.main(["summarize", "--output", str(self.output)]), 0)
        args = full.sanitized_arguments(
            "writers",
            output=self.output,
            concurrency=2,
            api_key="PRIVATE",
            environment="PRIVATE",
        )
        self.assertEqual(set(args), {"command", "output", "concurrency"})
        self.assertNotIn("PRIVATE", json.dumps(args))


if __name__ == "__main__":
    unittest.main()
