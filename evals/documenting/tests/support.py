"""Offline boundaries and synthetic data shared by the runner tests."""

from contextlib import nullcontext
import json
from pathlib import Path
import socket
import tempfile
import types
from typing import Optional
import unittest
from unittest.mock import patch


TESTS = Path(__file__).resolve().parent
RUNNER = TESTS.parent / "run.py"
# Loading source directly avoids creating a __pycache__ beside the runner,
# outside the test-only write boundary. __main__ is deliberately not executed.
run = types.ModuleType("documenting_runner_under_test")
run.__file__ = str(RUNNER)
exec(compile(RUNNER.read_text(), str(RUNNER), "exec"), run.__dict__)
# Transport tests exercise this function with Popen mocked, so no child starts.
EXECUTE = run.execute


class OfflineTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        for target, name in (
            (run, "isolated_runtime"),
            (run, "execute"),
            (run.subprocess, "Popen"),
            (run.subprocess, "check_output"),
            (socket, "socket"),
            (socket, "create_connection"),
        ):
            guard = patch.object(
                target, name, side_effect=AssertionError("Offline test reached " + name)
            )
            guard.start()
            self.addCleanup(guard.stop)


class ArtifactTestCase(OfflineTestCase):
    def setUp(self):
        super().setUp()
        temp = tempfile.TemporaryDirectory(prefix="offline-", dir=str(TESTS))
        self.addCleanup(temp.cleanup)
        self.output = Path(temp.name)

    def call_with_stdout(self, folder, stdout, code=0, timed_out=False):
        with (
            patch.object(
                run,
                "isolated_runtime",
                return_value=nullcontext(("offline-opencode", self.output, {})),
            ),
            patch.object(
                run,
                "execute",
                autospec=EXECUTE,
                return_value=(stdout, "synthetic stderr", code, timed_out, 2.5),
            ) as execute,
        ):
            result, text = run.call_model(
                folder, "Assigned system", "Supplied draft", "offline/model", None, 10
            )
        execute.assert_called_once()
        self.assertEqual(execute.call_args.kwargs.get("input_text"), "Supplied draft")
        return result, text


def judgment(case):
    def candidate():
        return {
            "requirements": [
                {
                    "id": item["id"],
                    "status": "pass",
                    "evidence": "Supplied fact retained.",
                }
                for item in case["requirements"]
            ],
            "issues": [
                {
                    "id": item["id"],
                    "status": "resolved",
                    "evidence": "Duplicate removed.",
                }
                for item in case["issues"]
            ],
            "regressions": [],
            "organization": 5,
            "unnecessary_change": 0,
        }

    return {
        "candidates": {"left": candidate(), "right": candidate()},
        "winner": "tie",
        "reason": "Both preserve the supplied facts.",
    }


def text_event(text="Final document", part_id="text-1"):
    return {
        "type": "text",
        "sessionID": "offline-session",
        "timestamp": 2000,
        "part": {
            "id": part_id,
            "messageID": "message-1",
            "sessionID": "offline-session",
            "type": "text",
            "text": text,
            "time": {"start": 1000, "end": 2000},
        },
    }


def finish_event(part_id="finish-1", reason: Optional[str] = "stop"):
    # v1.18.31 Session.getUsage already excludes reasoning from output and cache
    # from input. `total` overlaps the five buckets; it is not a sixth bucket.
    return {
        "type": "step_finish",
        "sessionID": "offline-session",
        "timestamp": 2001,
        "part": {
            "id": part_id,
            "messageID": "message-1",
            "sessionID": "offline-session",
            "type": "step-finish",
            "reason": reason,
            "cost": 0.125,
            "tokens": {
                "input": 100,
                "output": 40,
                "reasoning": 60,
                "cache": {"read": 80, "write": 20},
                "total": 300,
            },
        },
    }


def jsonl(*events):
    return "".join(json.dumps(event) + "\n" for event in events)
