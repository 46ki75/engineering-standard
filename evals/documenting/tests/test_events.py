"""CLI event retention, nonoverlapping usage, and failed-trial artifacts."""

import argparse
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import json
from unittest.mock import Mock, patch

from support import (
    ArtifactTestCase,
    EXECUTE,
    OfflineTestCase,
    finish_event,
    jsonl,
    run,
    text_event,
)


class EventMetricsTests(OfflineTestCase):
    def test_usage_comes_from_step_finishes_not_cumulative_message_snapshots(self):
        first = finish_event()
        second = finish_event("finish-2", "end_turn")
        second["part"]["cost"] = 0.25
        second["part"]["tokens"] = {
            "input": 7,
            "output": 11,
            "reasoning": 13,
            "cache": {"read": 17, "write": 19},
            "total": 67,
        }
        # A repeated assistant snapshot must not count the same usage again.
        # run --format json currently does not emit these; guard against later
        # exporters/adapters mixing snapshots with its per-step events.
        snapshot = {
            "type": "message.updated",
            "properties": {
                "info": {
                    "role": "assistant",
                    "cost": 0.375,
                    "tokens": {
                        "input": 107,
                        "output": 51,
                        "reasoning": 73,
                        "cache": {"read": 97, "write": 39},
                        "total": 367,
                    },
                }
            },
        }
        events = [text_event(), first, snapshot, deepcopy(snapshot), second]
        original = deepcopy(events)
        metrics = run.event_metrics(events)
        self.assertEqual(
            metrics["tokens"],
            {
                "input": 107,
                "output": 51,
                "reasoning": 73,
                "cache_read": 97,
                "cache_write": 39,
            },
        )
        self.assertEqual(sum(metrics["tokens"].values()), 367)
        self.assertEqual(metrics["observed_model_steps"], 2)
        self.assertAlmostEqual(metrics["reported_cost"], 0.375)
        self.assertEqual(metrics["finish_reasons"], ["stop", "end_turn"])
        self.assertEqual(events, original)

    def test_malformed_usage_does_not_erase_valid_usage_or_count_as_a_model_step(self):
        missing = {"type": "step_finish", "part": {"reason": "stop"}}
        null_counts = {
            "type": "step_finish",
            "part": {
                "reason": "end_turn",
                "cost": None,
                "tokens": {
                    "input": None,
                    "output": None,
                    "reasoning": None,
                    "cache": {"read": None, "write": None},
                },
            },
        }
        events, _ = run.parse_events(jsonl(finish_event(), missing, null_counts))
        self.assertEqual(sum(event["type"] == "malformed" for event in events), 2)
        metrics = run.event_metrics(events)
        self.assertEqual(
            metrics["tokens"],
            {
                "input": 100,
                "output": 40,
                "reasoning": 60,
                "cache_read": 80,
                "cache_write": 20,
            },
        )
        self.assertEqual(metrics["observed_model_steps"], 1)
        self.assertAlmostEqual(metrics["reported_cost"], 0.125)

    def test_reasoning_text_is_filtered_without_losing_reasoning_token_counts(self):
        reasoning = {
            "type": "reasoning",
            "part": {"text": "PRIVATE-REASONING-SENTINEL"},
        }
        stdout = (
            "startup noise\n"
            + jsonl(reasoning, text_event(), finish_event())
            + "{broken\n"
        )
        events, noise = run.parse_events(stdout)
        self.assertEqual(events, [text_event(), finish_event()])
        self.assertEqual(noise, ["startup noise", "{broken"])
        self.assertNotIn("PRIVATE-REASONING-SENTINEL", json.dumps([events, noise]))
        self.assertEqual(run.event_metrics(events)["tokens"]["reasoning"], 60)

    def test_empty_and_non_json_streams_have_no_observed_model_steps(self):
        for stdout, expected_noise in (
            ("", []),
            ("startup\n{broken\n", ["startup", "{broken"]),
        ):
            with self.subTest(stdout=stdout):
                events, noise = run.parse_events(stdout)
                self.assertEqual(events, [])
                self.assertEqual(noise, expected_noise)
                metrics = run.event_metrics(events)
                self.assertEqual(metrics["observed_model_steps"], 0)
                self.assertEqual(metrics["finish_reasons"], [])
                self.assertEqual(sum(metrics["tokens"].values()), 0)


class CallModelTests(ArtifactTestCase):
    def test_exact_prompt_reaches_subprocess_stdin_without_a_positional_message(self):
        prompt = '  # Draft: "quoted" café\n\n```json\n{"path": "C:\\\\tmp"}\n```\n\t'
        process = Mock(returncode=0)
        process.communicate.return_value = (jsonl(text_event(), finish_event()), "")
        folder = self.output / "transport"
        with (
            patch.object(
                run,
                "isolated_runtime",
                return_value=nullcontext(("offline-opencode", self.output, {})),
            ),
            patch.object(run, "execute", wraps=EXECUTE) as execute,
            patch.object(run.subprocess, "Popen", return_value=process) as popen,
        ):
            result, _ = run.call_model(
                folder, "Assigned system", prompt, "offline/model", "high", 10
            )
        execute.assert_called_once()
        self.assertEqual(execute.call_args.kwargs.get("input_text"), prompt)
        popen.assert_called_once()
        command = popen.call_args.args[0]
        self.assertEqual(command[1], "run")
        # Parse the public CLI options rather than asserting incidental option
        # ordering, executable paths, titles, or the custom agent's name.
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--pure", action="store_true")
        for option in ("--agent", "--model", "--format", "--title", "--variant"):
            parser.add_argument(option)
        options, remaining = parser.parse_known_args(command[2:])
        self.assertEqual(remaining, [], "Unexpected positional message or CLI argument")
        self.assertEqual(options.model, "offline/model")
        self.assertEqual(options.variant, "high")
        self.assertEqual(popen.call_args.kwargs["stdin"], run.subprocess.PIPE)
        self.assertTrue(popen.call_args.kwargs["text"])
        process.communicate.assert_called_once_with(input=prompt, timeout=10)
        self.assertEqual((folder / "input.md").read_bytes(), prompt.encode("utf-8"))
        self.assertEqual(
            result["input_sha256"], hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        )
        self.assertEqual(result["status"], "completed")

    def test_completed_document_retains_usage_and_artifacts_without_reasoning_text(
        self,
    ):
        reasoning = {
            "type": "reasoning",
            "part": {"text": "PRIVATE-REASONING-SENTINEL"},
        }
        stdout = "startup noise\n" + jsonl(
            reasoning,
            text_event("# Final"),
            text_event("Required context.", "text-2"),
            finish_event(),
        )
        folder = self.output / "trial"
        result, text = self.call_with_stdout(folder, stdout)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(text, "# Final\nRequired context.")
        self.assertEqual(
            result["tokens"],
            {
                "input": 100,
                "output": 40,
                "reasoning": 60,
                "cache_read": 80,
                "cache_write": 20,
            },
        )
        self.assertEqual(result["observed_model_steps"], 1)
        self.assertEqual(json.loads((folder / "result.json").read_text()), result)
        self.assertEqual((folder / "output.md").read_text(), text)
        self.assertEqual((folder / "stdout-noise.txt").read_text(), "startup noise")
        retained = [
            json.loads(line)
            for line in (folder / "events.jsonl").read_text().splitlines()
        ]
        self.assertEqual(
            [event["type"] for event in retained], ["text", "text", "step_finish"]
        )
        for artifact in folder.iterdir():
            self.assertNotIn("PRIVATE-REASONING-SENTINEL", artifact.read_text())

    def test_failed_transports_keep_partial_usage_and_cannot_be_silently_resumed(self):
        for index, (code, timed_out) in enumerate(((1, False), (0, True))):
            with self.subTest(code=code, timed_out=timed_out):
                folder = self.output / str(index)
                result, text = self.call_with_stdout(
                    folder, jsonl(text_event(), finish_event()), code, timed_out
                )
                self.assertEqual(result["status"], "failed")
                self.assertIn("CLI exit or timeout", result["failures"])
                self.assertEqual(result["tokens"]["input"], 100)
                self.assertEqual(text, "Final document")
                self.assertEqual(
                    json.loads((folder / "result.json").read_text()), result
                )
                with self.assertRaisesRegex(
                    ValueError, "Failed/incomplete trial retained"
                ):
                    run.existing(folder)

    def test_error_and_tool_events_invalidate_an_otherwise_complete_response(self):
        for kind in ("tool_use", "error"):
            with self.subTest(kind=kind):
                folder = self.output / kind
                result, _ = self.call_with_stdout(
                    folder, jsonl(text_event(), {"type": kind}, finish_event())
                )
                self.assertEqual(result["status"], "failed")
                self.assertTrue(result["failures"])
                self.assertEqual(result["observed_model_steps"], 1)
                self.assertEqual(result["tokens"]["reasoning"], 60)

    def test_empty_whitespace_noise_only_and_missing_or_extra_finishes_fail(self):
        streams = (
            "",
            "startup\n{broken\n",
            jsonl(finish_event()),
            jsonl(text_event(" \n\t"), finish_event()),
            jsonl(text_event()),
            jsonl(text_event(), finish_event(), finish_event("finish-2")),
            jsonl(
                {"type": "reasoning", "part": {"text": "Only reasoning"}},
                finish_event(),
            ),
        )
        for index, stdout in enumerate(streams):
            with self.subTest(index=index):
                folder = self.output / str(index)
                result, _ = self.call_with_stdout(folder, stdout)
                self.assertEqual(result["status"], "failed")
                self.assertIn(
                    "empty response or unexpected model step count", result["failures"]
                )
                self.assertEqual(
                    json.loads((folder / "result.json").read_text()), result
                )

    def test_truncated_or_tool_continuation_finishes_are_not_successes(self):
        for index, reason in enumerate(
            ("stop", "end_turn", "length", "tool-calls", "error", None)
        ):
            with self.subTest(reason=reason):
                result, _ = self.call_with_stdout(
                    self.output / str(index),
                    jsonl(text_event(), finish_event(reason=reason)),
                )
                self.assertEqual(
                    result["status"],
                    "completed" if reason in ("stop", "end_turn") else "failed",
                )
                if result["status"] == "failed":
                    self.assertIn("unexpected finish reason", result["failures"])

    def test_nonobject_json_event_is_recorded_as_failed_without_losing_usage(self):
        folder = self.output / "malformed"
        result, _ = self.call_with_stdout(
            folder, jsonl(text_event(), finish_event(), None)
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["tokens"]["input"], 100)
        self.assertEqual(json.loads((folder / "result.json").read_text()), result)

    def test_malformed_text_event_is_recorded_as_failed_without_losing_usage(self):
        folder = self.output / "malformed"
        result, _ = self.call_with_stdout(
            folder, jsonl(finish_event(), {"type": "text", "part": {}})
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["tokens"]["reasoning"], 60)
        self.assertEqual(json.loads((folder / "result.json").read_text()), result)
