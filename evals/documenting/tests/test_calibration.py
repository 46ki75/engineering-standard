"""Offline scheduling, blinding, invalid judge retention, and budget summaries."""

from contextlib import nullcontext, redirect_stdout
from copy import deepcopy
import io
import json
from unittest.mock import Mock, patch

from support import ArtifactTestCase, EXECUTE, judgment, run


class CalibrationTests(ArtifactTestCase):
    def setUp(self):
        super().setUp()
        self.frozen = run.initialize(self.output)

    def record_trial(self, folder, text, status="completed"):
        folder.mkdir(parents=True)
        (folder / "output.md").write_text(text)
        result = {
            "status": status,
            "failures": [] if status == "completed" else ["synthetic failure"],
            "seconds": 2.5,
            "observed_model_steps": 1,
            "reported_cost": 0.125,
            "output_words": len(text.split()),
            "tokens": {
                "input": 100,
                "output": 40,
                "reasoning": 60,
                "cache_read": 80,
                "cache_write": 20,
            },
        }
        (folder / "result.json").write_text(json.dumps(result))
        return result, text

    def fake_writer(self, folder, system, prompt, model, variant, timeout):
        case = next(c for c in self.frozen["inputs"]["cases"] if c["task"] in prompt)
        arm = folder.name[-1]
        self.assertEqual(system, self.frozen["inputs"]["systems"][arm])
        self.assertEqual(model, run.WRITER_MODEL)
        self.assertEqual(variant, run.WRITER_VARIANT)
        self.assertEqual(prompt, run.writer_prompt(case))
        # Distinguishable documents let the swap assertions catch accidental
        # reuse of one side, without adding arm labels to the judge's input.
        text = case["draft"] + "\n" + "End of document.\n" * ("ABC".index(arm) + 1)
        return self.record_trial(folder, text)

    def populate_writers(self):
        with (
            patch.object(run, "call_model", side_effect=self.fake_writer),
            redirect_stdout(io.StringIO()),
        ):
            run.writers(self.output, self.frozen, concurrency=1, limit=None, timeout=10)

    def test_nine_writers_twelve_blinded_judges_resume_and_position_bias_accounting(
        self,
    ):
        expected_jobs = {
            (case["id"], arm)
            for case in self.frozen["inputs"]["cases"]
            for arm in "ABC"
        }
        self.assertEqual(len(self.frozen["writer_order"]), 9)
        self.assertEqual(set(map(tuple, self.frozen["writer_order"])), expected_jobs)
        with (
            patch.object(run, "call_model", side_effect=self.fake_writer) as writer,
            redirect_stdout(io.StringIO()),
        ):
            run.writers(self.output, self.frozen, concurrency=1, limit=1, timeout=10)
            self.assertEqual(writer.call_count, 1)
            run.writers(self.output, self.frozen, concurrency=2, limit=None, timeout=10)
            self.assertEqual(writer.call_count, 9)
            run.writers(self.output, self.frozen, concurrency=1, limit=None, timeout=10)
            self.assertEqual(writer.call_count, 9)
        self.assertEqual(
            {call.args[0].name for call in writer.call_args_list},
            {case_id + "-" + arm for case_id, arm in expected_jobs},
        )

        def fake_judge(folder, system, prompt, model, variant, timeout):
            payload = json.loads(prompt)
            case = next(
                c
                for c in self.frozen["inputs"]["cases"]
                if c["task"] == payload["task"]
            )
            self.assertEqual(
                set(payload),
                {
                    "task",
                    "source_facts",
                    "draft",
                    "requirements",
                    "issues",
                    "candidates",
                },
            )
            self.assertEqual(set(payload["candidates"]), {"left", "right"})
            self.assertEqual(system, self.frozen["inputs"]["judge_system"])
            self.assertEqual(model, run.JUDGE_MODEL)
            self.assertIsNone(variant)
            left, right = folder.name[-2:]
            for side, arm in (("left", left), ("right", right)):
                expected = (
                    self.output / "writers" / (case["id"] + "-" + arm) / "output.md"
                )
                self.assertEqual(payload["candidates"][side], expected.read_text())
            for field in ("source_facts", "draft", "requirements", "issues"):
                self.assertEqual(payload[field], case[field])
            value = judgment(case)
            value["winner"] = "left"
            return self.record_trial(folder, json.dumps(value))

        with (
            patch.object(run, "call_model", side_effect=fake_judge) as judge,
            redirect_stdout(io.StringIO()),
        ):
            run.judge(self.output, self.frozen, concurrency=2, limit=None, timeout=10)
            self.assertEqual(judge.call_count, 12)
            run.judge(self.output, self.frozen, concurrency=1, limit=None, timeout=10)
            self.assertEqual(judge.call_count, 12)
            run.summarize(self.output, self.frozen)
        expected_judges = {
            case["id"] + "-" + order
            for case in self.frozen["inputs"]["cases"]
            for order in ("AB", "BA", "BC", "CB")
        }
        self.assertEqual(
            {call.args[0].name for call in judge.call_args_list}, expected_judges
        )
        for path in (self.output / "judges").glob("*/mapping.json"):
            mapping = json.loads(path.read_text())
            self.assertEqual(
                path.parent.name,
                mapping["case"] + "-" + mapping["left"] + mapping["right"],
            )

        summary = json.loads((self.output / "summary.json").read_text())
        self.assertEqual(len(summary["writers"]), 9)
        self.assertEqual(len(summary["comparisons"]), 6)
        for comparison in summary["comparisons"]:
            self.assertFalse(comparison["order_agrees"])
            self.assertEqual(len(comparison["votes"]), 2)
            self.assertEqual(
                {v["winner"] for v in comparison["votes"]}, set(comparison["pair"])
            )
            for vote in comparison["votes"]:
                self.assertEqual(vote["winner"], vote["order"][0])
        for kind, count, expected_tokens, cost in (
            (
                "writers",
                9,
                {
                    "input": 900,
                    "output": 360,
                    "reasoning": 540,
                    "cache_read": 720,
                    "cache_write": 180,
                },
                1.125,
            ),
            (
                "judges",
                12,
                {
                    "input": 1200,
                    "output": 480,
                    "reasoning": 720,
                    "cache_read": 960,
                    "cache_write": 240,
                },
                1.5,
            ),
        ):
            usage = summary["usage"][kind]
            self.assertEqual(usage["sessions"], count)
            self.assertEqual(usage["completed"], count)
            self.assertEqual(usage["observed_model_steps"], count)
            self.assertEqual(usage["tokens"], expected_tokens)
            self.assertAlmostEqual(usage["reported_cost"], cost)

        for kind, sessions, hours, cost, tokens in (
            (
                "writers",
                324,
                0.225,
                40.5,
                {
                    "input": 32400,
                    "output": 12960,
                    "reasoning": 19440,
                    "cache_read": 25920,
                    "cache_write": 6480,
                },
            ),
            (
                "judges",
                270,
                0.1875,
                33.75,
                {
                    "input": 27000,
                    "output": 10800,
                    "reasoning": 16200,
                    "cache_read": 21600,
                    "cache_write": 5400,
                },
            ),
        ):
            projection = summary["full_suite_projection"][kind]
            self.assertEqual(projection["sessions"], sessions)
            self.assertAlmostEqual(projection["serial_hours"], hours)
            self.assertAlmostEqual(
                projection["reported_cost_projection_not_billing"], cost
            )
            self.assertEqual(projection["tokens"], tokens)

    def test_order_swaps_keep_arm_identity_ties_uncertainty_and_missing_pairs(self):
        case = self.frozen["inputs"]["cases"][0]
        scenarios = (
            (("left", "right"), ["A", "A"], True),
            (("tie", "tie"), ["tie", "tie"], True),
            (("uncertain", "uncertain"), ["uncertain", "uncertain"], True),
            (("left",), ["A"], False),
        )
        for index, (winners, expected, agrees) in enumerate(scenarios):
            with self.subTest(winners=winners):
                output = self.output / ("swaps-" + str(index))
                for order, winner in zip(("AB", "BA"), winners):
                    folder = output / "judges" / (case["id"] + "-" + order)
                    value = judgment(case)
                    value["winner"] = winner
                    self.record_trial(folder, json.dumps(value))
                    (folder / "judgment.json").write_text(json.dumps(value))
                with redirect_stdout(io.StringIO()):
                    run.summarize(output, self.frozen)
                summary = json.loads((output / "summary.json").read_text())
                comparison = next(
                    c
                    for c in summary["comparisons"]
                    if c["case"] == case["id"] and c["pair"] == "AB"
                )
                self.assertEqual(
                    [vote["winner"] for vote in comparison["votes"]], expected
                )
                self.assertEqual(comparison["order_agrees"], agrees)

    def test_bad_judge_json_is_retained_as_failure_including_usage(self):
        invalid = (
            "",
            "not JSON",
            "```json\n{}\n```",
            "{} trailing prose",
            "{}{}",
            '{"candidates":',
            "null",
            "[]",
            "{}",
        )
        for index, text in enumerate(invalid):
            with self.subTest(text=text):
                # Each attempt gets a fresh output tree; a prior failure must
                # never be overwritten merely to make the next example run.
                output = self.output / ("invalid-" + str(index))
                for case in self.frozen["inputs"]["cases"]:
                    for arm in "ABC":
                        self.record_trial(
                            output / "writers" / (case["id"] + "-" + arm), case["draft"]
                        )

                def fake_judge(folder, *args):
                    return self.record_trial(folder, text)

                with (
                    patch.object(run, "call_model", side_effect=fake_judge) as call,
                    redirect_stdout(io.StringIO()),
                ):
                    with self.assertRaisesRegex(
                        ValueError, "One or more judges failed"
                    ):
                        run.judge(
                            output, self.frozen, concurrency=1, limit=1, timeout=10
                        )
                call.assert_called_once()
                folder = call.call_args.args[0]
                result = json.loads((folder / "result.json").read_text())
                self.assertEqual(result["status"], "failed")
                self.assertTrue(result["failures"][0].startswith("Invalid judge JSON:"))
                self.assertEqual(result["tokens"]["reasoning"], 60)
                self.assertEqual((folder / "output.md").read_text(), text)
                self.assertFalse((folder / "judgment.json").exists())
                self.assertTrue((folder / "mapping.json").exists())
                with self.assertRaisesRegex(
                    ValueError, "Failed/incomplete trial retained"
                ):
                    run.existing(folder)

    def test_failed_judge_usage_is_included_without_becoming_a_vote(self):
        self.populate_writers()
        case = self.frozen["inputs"]["cases"][0]
        folder = self.output / "judges" / (case["id"] + "-AB")
        self.record_trial(folder, "Unusable response", status="failed")
        with redirect_stdout(io.StringIO()):
            run.summarize(self.output, self.frozen)
        summary = json.loads((self.output / "summary.json").read_text())
        usage = summary["usage"]["judges"]
        self.assertEqual(usage["sessions"], 1)
        self.assertEqual(usage["completed"], 0)
        self.assertEqual(usage["observed_model_steps"], 1)
        self.assertEqual(
            usage["tokens"],
            {
                "input": 100,
                "output": 40,
                "reasoning": 60,
                "cache_read": 80,
                "cache_write": 20,
            },
        )
        self.assertAlmostEqual(usage["reported_cost"], 0.125)
        self.assertTrue(all(not c["votes"] for c in summary["comparisons"]))
        self.assertTrue(all(not c["order_agrees"] for c in summary["comparisons"]))

    def test_manifest_resume_preserves_schedule_but_rejects_changed_inputs(self):
        resumed = run.initialize(self.output)
        self.assertEqual(
            resumed["writer_order"], list(map(list, self.frozen["writer_order"]))
        )
        changed = deepcopy(self.frozen["inputs"])
        changed["systems"]["C"] += "\nNew treatment after seeing calibration."
        with patch.object(run, "load_inputs", return_value=changed):
            with self.assertRaisesRegex(ValueError, "Inputs or runner changed"):
                run.initialize(self.output)

    def test_missing_writer_prevents_any_judge_call(self):
        with patch.object(run, "call_model") as call:
            with self.assertRaisesRegex(ValueError, "Missing writer"):
                run.judge(self.output, self.frozen, concurrency=1, limit=1, timeout=10)
        call.assert_not_called()


class PreflightTests(ArtifactTestCase):
    def test_resolved_disabled_tools_pass_with_isolated_inspection_stdin(self):
        frozen = run.initialize(self.output)
        processes = []

        def runtime(config):
            return nullcontext(
                (
                    "offline-opencode",
                    self.output,
                    {"OPENCODE_CONFIG_CONTENT": json.dumps(config)},
                )
            )

        def inspection_stdout(command, env):
            # Support repeated writer/judge inspections without depending on
            # their order, filenames, agent names, or a fixed command count.
            # Unknown commands fail closed, never reaching a real executable.
            if command[1:] == ["--version"]:
                return run.VERSION
            config = json.loads(env["OPENCODE_CONFIG_CONTENT"])
            if command[1:3] == ["debug", "config"]:
                return json.dumps(config)
            if command[1:3] == ["debug", "paths"]:
                return json.dumps({"home": str(self.output)})
            if command[1:3] == ["debug", "skill"]:
                return "[]"
            if command[1:3] == ["debug", "agent"]:
                name = command[3]
                configured = config["agent"][name]
                provider, model = configured["model"].split("/", 1)
                # The source-verified flat object retains overridden defaults;
                # effective tool availability is the relevant invariant.
                return json.dumps(
                    {
                        **configured,
                        "name": name,
                        "model": {"providerID": provider, "modelID": model},
                        "permission": [
                            {"permission": "*", "pattern": "*", "action": "allow"},
                            {
                                "permission": "doom_loop",
                                "pattern": "*",
                                "action": "ask",
                            },
                            {"permission": "*", "pattern": "*", "action": "deny"},
                        ],
                        "tools": {
                            "bash": False,
                            "read": False,
                            "skill": False,
                            "apply_patch": False,
                        },
                    }
                )
            if command[1] == "models" and "--refresh" not in command:
                # v1.18.31 models --verbose prints an ID line, then its JSON
                # metadata. These synthetic records never query a provider.
                records = []
                for name in (run.WRITER_MODEL, run.JUDGE_MODEL):
                    provider, model = name.split("/", 1)
                    if (
                        len(command) > 2
                        and not command[2].startswith("-")
                        and command[2] != provider
                    ):
                        continue
                    records.append(name + "\n")
                    if "--verbose" in command:
                        records.append(
                            json.dumps(
                                {
                                    "id": model,
                                    "providerID": provider,
                                    "name": model,
                                    "api": {
                                        "id": model,
                                        "npm": "@ai-sdk/openai",
                                        "url": "https://offline.invalid",
                                    },
                                    "limit": {
                                        "context": 200000,
                                        "input": 200000,
                                        "output": 32768,
                                    },
                                    "capabilities": {
                                        "reasoning": True,
                                        "toolcall": True,
                                        "temperature": False,
                                    },
                                    "variants": {
                                        run.WRITER_VARIANT: {
                                            "reasoningEffort": run.WRITER_VARIANT
                                        }
                                    },
                                    "options": {},
                                },
                                indent=2,
                            )
                            + "\n"
                        )
                return "".join(records)
            self.fail("Unexpected offline inspection command: " + repr(command))

        def popen(command, **kwargs):
            self.assertEqual(kwargs.get("stdin"), run.subprocess.DEVNULL)
            process = Mock(returncode=0)
            process.communicate.return_value = (
                inspection_stdout(command, kwargs["env"]),
                "",
            )
            processes.append(process)
            return process

        def check_output(command, **kwargs):
            return inspection_stdout(command, kwargs["env"])

        with (
            patch.object(run, "isolated_runtime", side_effect=runtime),
            patch.object(
                run.subprocess, "check_output", side_effect=check_output
            ) as checked,
            patch.object(run.subprocess, "Popen", side_effect=popen),
            patch.object(run, "execute", wraps=EXECUTE),
            redirect_stdout(io.StringIO()),
        ):
            run.preflight(self.output, frozen)
        self.assertTrue((self.output / "preflight.json").exists())
        self.assertTrue(processes)
        for process in processes:
            process.communicate.assert_called_once()
            self.assertIsNone(process.communicate.call_args.kwargs.get("input"))
        for call in checked.call_args_list:
            self.assertEqual(call.kwargs.get("stdin"), run.subprocess.DEVNULL)
