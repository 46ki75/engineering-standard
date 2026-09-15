"""Offline, synthetic tests for the pinned native structured HTTP adapter."""

from contextlib import ExitStack, nullcontext
from copy import deepcopy
import io
import json
from pathlib import Path
import queue
import signal
import subprocess
import sys
import types
from typing import Optional
from unittest.mock import Mock, call, patch

from support import ArtifactTestCase, OfflineTestCase, run


SOURCE = Path(__file__).resolve().parents[1] / "structured.py"
structured = types.ModuleType("structured_under_test")
structured.__file__ = str(SOURCE)
with patch.dict(sys.modules, {"run": run}):
    exec(compile(SOURCE.read_text(), str(SOURCE), "exec"), structured.__dict__)
INPUT_AUDIT = structured._InputAudit

MODEL = "offline/model"
SESSION = "ses_offline"
SYSTEM = 'Judge only the supplied text.\r\n"Quoted" café\n'
PROMPT = '  # Input "quoted" café\r\n\n```json\n{"x":"C:\\\\tmp"}\n```\n\t'
SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean", "const": True}},
    "required": ["ok"],
    "additionalProperties": False,
}
SECRET = "PRIVATE-REASONING-PROVIDER-SECRET-SENTINEL"


def response():
    usage = {
        "cost": 0.125,
        "tokens": {
            "input": 100,
            "output": 7,
            "reasoning": 11,
            "cache": {"read": 19, "write": 23},
            "total": 160,
        },
    }

    def part(kind, suffix, **fields):
        return {
            "id": "prt_" + suffix,
            "messageID": "msg_assistant",
            "sessionID": SESSION,
            "type": kind,
            **fields,
        }

    return {
        "info": {
            "id": "msg_assistant",
            "sessionID": SESSION,
            "parentID": "msg_user",
            "role": "assistant",
            "providerID": "offline",
            "modelID": "model",
            "agent": structured.AGENT,
            "mode": structured.AGENT,
            "variant": "high",
            "time": {"created": 1000, "completed": 2000},
            "finish": "tool-calls",
            "structured": {"ok": True},
            **deepcopy(usage),
        },
        "parts": [
            part("step-start", "start"),
            part("reasoning", "reasoning", text=SECRET, metadata={"encrypted": SECRET}),
            part(
                "text",
                "text",
                text="Final answer follows.",
                metadata={"provider": SECRET},
            ),
            part(
                "tool",
                "tool",
                tool="StructuredOutput",
                callID="call_1",
                state={
                    "status": "completed",
                    "input": {"ok": True},
                    "output": structured.TOOL_OUTPUT,
                    "title": "Structured Output",
                    "metadata": {"valid": True},
                    "time": {"start": 1500, "end": 1800},
                },
            ),
            part("step-finish", "finish", reason="tool-calls", **deepcopy(usage)),
        ],
    }


def history(answer, prompt=PROMPT, variant: Optional[str] = "high"):
    model = {"providerID": "offline", "modelID": "model"}
    if variant is not None:
        model["variant"] = variant
    return [
        {
            "info": {
                "id": "msg_user",
                "sessionID": SESSION,
                "role": "user",
                "agent": structured.AGENT,
                "model": model,
                "format": {
                    "type": "json_schema",
                    "schema": deepcopy(SCHEMA),
                    "retryCount": 0,
                },
            },
            "parts": [
                {
                    "type": "text",
                    "text": prompt,
                    "id": "prt_user",
                    "sessionID": SESSION,
                    "messageID": "msg_user",
                }
            ],
        },
        deepcopy(answer),
    ]


class CallStructuredTests(ArtifactTestCase):
    def invoke(
        self,
        name="trial",
        answer=None,
        audit=None,
        fail_at=None,
        error=None,
        startup_error=None,
        variant: Optional[str] = "high",
        runtime_error=None,
    ):
        answer = response() if answer is None else answer
        audit = history(answer, variant=variant) if audit is None else audit
        calls = []
        process = Mock(pid=24680, returncode=-signal.SIGTERM)
        process.poll.return_value = None
        process.stdout = io.BytesIO()

        def request(port, method, path, payload=None, timeout=600):
            calls.append((method, path, deepcopy(payload)))
            self.assertEqual(port, 45678)
            self.assertGreater(timeout, 0)
            if fail_at == (method, path):
                assert isinstance(error, BaseException)
                raise error
            if (method, path) == ("POST", "/session"):
                return {"id": SESSION, "title": structured.AGENT}
            if path == "/session/" + SESSION + "/message":
                return deepcopy(answer if method == "POST" else audit)
            if (method, path) == ("POST", "/session/" + SESSION + "/abort"):
                return True
            raise AssertionError("Unexpected HTTP request")

        def terminate(child):
            self.assertIs(child, process)
            calls.append(("terminate", child.pid, None))

        def subscribe(*args):
            calls.append(("subscribe", "/event", None))
            collector = INPUT_AUDIT(*args)

            def finish(answer):
                calls.append(("audit", "/event", None))
                if fail_at == ("audit", "/event"):
                    assert isinstance(error, BaseException)
                    raise error
                if not isinstance(audit, list):
                    raise ValueError
                for item in audit:
                    collector._consume(
                        {
                            "type": "message.updated",
                            "properties": {"info": item["info"]},
                        }
                    )
                    for part in item["parts"]:
                        collector._consume(
                            {
                                "type": "message.part.updated",
                                "properties": {"part": part},
                            }
                        )
                if answer.get("info", {}).get("id") not in collector.completed:
                    collector.failed = True
                return collector.finish(answer)

            return nullcontext(Mock(finish=Mock(side_effect=finish)))

        folder = self.output / name
        with ExitStack() as stack:
            runtime = stack.enter_context(
                patch.object(
                    run,
                    "isolated_runtime",
                    return_value=nullcontext(
                        ("offline-opencode", self.output, {"TEST": "isolated"})
                    ),
                    side_effect=runtime_error,
                )
            )
            stack.enter_context(
                patch.object(structured, "_free_port", return_value=45678)
            )
            popen = stack.enter_context(
                patch.object(structured.subprocess, "Popen", return_value=process)
            )
            stack.enter_context(
                patch.object(structured, "_wait_ready", side_effect=startup_error)
            )
            stack.enter_context(
                patch.object(structured, "_request", side_effect=request)
            )
            stack.enter_context(
                patch.object(structured, "_InputAudit", side_effect=subscribe)
            )
            stop = stack.enter_context(
                patch.object(structured, "_terminate", side_effect=terminate)
            )
            result, value = structured.call_structured(
                folder, SYSTEM, PROMPT, SCHEMA, MODEL, variant, timeout=10
            )
        return result, value, folder, calls, runtime, popen, stop

    def assert_retained_failure(self, invoked):
        result, value, folder = invoked[:3]
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["failures"])
        self.assertIsNone(value)
        self.assertEqual((folder / "output.md").read_bytes(), b"")
        self.assertFalse((folder / "structured.json").exists())
        self.assertEqual(json.loads((folder / "result.json").read_text()), result)
        self.assertEqual(result["output_sha256"], run.digest(""))
        for artifact in folder.iterdir():
            self.assertNotIn(SECRET, artifact.read_text())

    def test_exact_wire_payload_config_and_artifacts(self):
        result, value, folder, calls, runtime, popen, stop = self.invoke()
        self.assertEqual(result["status"], "completed", result["failures"])
        self.assertEqual(value, {"ok": True})
        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(result["actual_input_match"])
        self.assertTrue(result["session_isolated"])
        self.assertEqual(result["session_ids"], [SESSION])
        self.assertEqual(result["prompt_posts"], 1)
        self.assertEqual((folder / "input.md").read_bytes(), PROMPT.encode("utf-8"))
        self.assertEqual((folder / "system.md").read_bytes(), SYSTEM.encode("utf-8"))
        self.assertEqual(result["input_sha256"], run.digest(PROMPT))
        self.assertEqual(result["system_sha256"], run.digest(SYSTEM))
        self.assertEqual(json.loads((folder / "schema.json").read_text()), SCHEMA)
        config = json.loads((folder / "config.json").read_text())
        self.assertEqual(config, runtime.call_args.args[0])
        expected = run.configuration(SYSTEM, MODEL)
        expected["permission"] = {"*": "deny", "StructuredOutput": "allow"}
        expected["agent"][structured.AGENT]["permission"] = expected[
            "permission"
        ].copy()
        self.assertEqual(config, expected)
        self.assertEqual(
            list(config["permission"].items()),
            [("*", "deny"), ("StructuredOutput", "allow")],
        )
        self.assertEqual(calls[0], ("POST", "/session", {"title": structured.AGENT}))
        self.assertEqual(
            calls[2],
            (
                "POST",
                "/session/" + SESSION + "/message",
                {
                    "model": {"providerID": "offline", "modelID": "model"},
                    "agent": structured.AGENT,
                    "variant": "high",
                    "parts": [{"type": "text", "text": PROMPT}],
                    "format": {
                        "type": "json_schema",
                        "schema": SCHEMA,
                        "retryCount": 0,
                    },
                },
            ),
        )
        self.assertEqual(
            [item[0] for item in calls],
            ["POST", "subscribe", "POST", "audit", "POST", "terminate"],
        )
        self.assertTrue(calls[-2][1].endswith("/abort"))
        popen.assert_called_once()
        args = popen.call_args
        self.assertEqual(
            args.args[0],
            [
                "offline-opencode",
                "serve",
                "--hostname",
                "127.0.0.1",
                "--port",
                "45678",
                "--pure",
            ],
        )
        self.assertTrue(args.kwargs["start_new_session"])
        self.assertEqual(args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(args.kwargs["stderr"], subprocess.DEVNULL)
        self.assertEqual(args.kwargs["cwd"], self.output)
        self.assertEqual(args.kwargs["env"], {"TEST": "isolated"})
        stop.assert_called_once()
        output = (folder / "output.md").read_text()
        self.assertEqual(json.loads(output), value)
        self.assertEqual(json.loads((folder / "structured.json").read_text()), value)
        self.assertEqual(result["output_sha256"], run.digest(output))
        self.assertEqual(result["output_words"], len(output.split()))
        self.assertEqual(json.loads((folder / "result.json").read_text()), result)

    def test_whitelists_remove_nested_metadata_errors_and_reasoning(self):
        answer = response()
        answer["providerMetadata"] = {"secret": SECRET}
        answer["info"].update(
            {"reasoning": SECRET, "encrypted": SECRET, "path": {"cwd": SECRET}}
        )
        answer["info"]["tokens"]["provider"] = SECRET
        answer["info"]["tokens"]["cache"]["encrypted"] = SECRET
        answer["info"]["time"]["metadata"] = SECRET
        for part in answer["parts"]:
            part["metadata"] = {"reasoning": SECRET}
            part["snapshot"] = SECRET
            if part["type"] == "tool":
                part["state"]["metadata"]["provider"] = {"encrypted": SECRET}
                part["state"]["raw"] = SECRET
                part["state"]["time"]["secret"] = SECRET
                part["state"]["title"] = SECRET
        result, _, folder = self.invoke(answer=answer)[:3]
        self.assertEqual(result["status"], "completed", result["failures"])
        for artifact in folder.iterdir():
            self.assertNotIn(SECRET, artifact.read_text())
        safe = json.loads((folder / "response.json").read_text())
        self.assertNotIn("structured", safe["info"])
        self.assertEqual(
            [part["type"] for part in safe["parts"]],
            ["step-start", "text", "tool", "step-finish"],
        )
        tool = next(part for part in safe["parts"] if part["type"] == "tool")
        self.assertEqual(tool["state"]["metadata"], {"valid": True})

    def test_usage_is_not_counted_twice_and_events_are_runner_compatible(self):
        result, _, folder = self.invoke()[:3]
        events = [
            json.loads(line)
            for line in (folder / "events.jsonl").read_text().splitlines()
        ]
        metrics = run.event_metrics(events)
        for key in (
            "tokens",
            "observed_model_steps",
            "reported_cost",
            "finish_reasons",
        ):
            self.assertEqual(result[key], metrics[key])
        self.assertEqual(
            result["tokens"],
            {
                "input": 100,
                "output": 7,
                "reasoning": 11,
                "cache_read": 19,
                "cache_write": 23,
            },
        )
        self.assertEqual(result["observed_model_steps"], 1)
        self.assertEqual(result["reported_cost"], 0.125)
        self.assertEqual(result["finish_reasons"], ["tool-calls"])
        self.assertIn("unavailable", result["provider_attempts"])

    def test_message_usage_fallback_is_once_and_labeled(self):
        answer = response()
        answer["parts"] = [p for p in answer["parts"] if p["type"] != "step-finish"]
        result, _, folder = self.invoke(answer=answer)[:3]
        self.assertEqual(result["status"], "completed", result["failures"])
        self.assertEqual(result["tokens"]["input"], 100)
        events = [
            json.loads(line)
            for line in (folder / "events.jsonl").read_text().splitlines()
        ]
        self.assertEqual(events[-1]["source"], "message_info")
        self.assertEqual(run.event_metrics(events)["observed_model_steps"], 1)

    def test_malformed_parts_preserve_available_message_usage(self):
        answer = response()
        answer["parts"] = None
        invoked = self.invoke(answer=answer)
        self.assert_retained_failure(invoked)
        self.assertEqual(invoked[0]["tokens"]["input"], 100)
        self.assertEqual(invoked[0]["reported_cost"], 0.125)

    def test_structured_input_fallback_and_none_variant(self):
        answer = response()
        del answer["info"]["structured"]
        del answer["info"]["variant"]
        invoked = self.invoke(answer=answer, variant=None)
        self.assertEqual(invoked[0]["status"], "completed", invoked[0]["failures"])
        self.assertEqual(invoked[1], {"ok": True})
        self.assertNotIn("variant", invoked[3][2][2])

    def test_tool_protocol_failures_are_retained(self):
        cases = []
        for name in ("bash", "structuredoutput", "StructuredOutputExtra"):
            answer = response()
            answer["parts"][3]["tool"] = name
            answer["parts"][3]["state"]["input"] = {"secret": SECRET}
            cases.append(answer)
        for status in ("pending", "running", "error"):
            answer = response()
            answer["parts"][3]["state"]["status"] = status
            answer["parts"][3]["state"]["error"] = SECRET
            cases.append(answer)
        answer = response()
        extra = deepcopy(answer["parts"][3])
        extra["id"] = "prt_second_tool"
        answer["parts"].append(extra)
        cases.append(answer)
        answer = response()
        answer["parts"] = [p for p in answer["parts"] if p["type"] != "tool"]
        cases.append(answer)
        for field, value in (
            ("metadata", {}),
            ("output", SECRET),
            ("input", []),
            ("attachments", [{"url": SECRET}]),
        ):
            answer = response()
            answer["parts"][3]["state"][field] = value
            cases.append(answer)
        for index, answer in enumerate(cases):
            with self.subTest(index=index):
                self.assert_retained_failure(self.invoke(str(index), answer=answer))

    def test_mismatched_structured_value_is_not_accepted(self):
        for index, value in enumerate(({"ok": False}, {"ok": 1}, [], None)):
            answer = response()
            answer["info"]["structured"] = value
            self.assert_retained_failure(self.invoke(str(index), answer=answer))

    def test_assistant_errors_are_sanitized_without_losing_usage(self):
        answer = response()
        answer["info"]["error"] = {
            "name": "APIError",
            "data": {
                "message": SECRET,
                "responseBody": SECRET,
                "responseHeaders": {"Authorization": SECRET},
                "metadata": {"secret": SECRET},
                "statusCode": 429,
                "isRetryable": True,
            },
        }
        invoked = self.invoke(answer=answer)
        self.assert_retained_failure(invoked)
        self.assertEqual(invoked[0]["tokens"]["input"], 100)
        safe = json.loads((invoked[2] / "response.json").read_text())
        self.assertEqual(
            safe["info"]["error"],
            {
                "name": "APIError",
                "data": {"statusCode": 429, "isRetryable": True},
            },
        )

    def test_bad_identity_finish_usage_or_extra_parts_fail(self):
        cases = []
        for key, value in (
            ("id", "bad/id"),
            ("sessionID", "ses_other"),
            ("role", "user"),
            ("providerID", "other"),
            ("modelID", "other"),
            ("agent", "build"),
            ("variant", "low"),
            ("finish", "length"),
            ("time", {"created": 1000}),
        ):
            answer = response()
            answer["info"][key] = value
            cases.append(answer)
        for value in (None, -1, True, float("inf"), float("nan")):
            answer = response()
            answer["info"]["tokens"]["input"] = value
            cases.append(answer)
        answer = response()
        answer["parts"][-1]["tokens"]["input"] = 101
        cases.append(answer)
        for kind in (
            "tool",
            "step-finish",
            "step-start",
            "file",
            "subtask",
            "retry",
            "compaction",
        ):
            answer = response()
            if kind in ("tool", "step-finish", "step-start"):
                extra = deepcopy(next(p for p in answer["parts"] if p["type"] == kind))
                if kind == "step-finish":
                    extra["id"] = "prt_extra_step"
            else:
                extra = {"type": kind, "text": SECRET}
            answer["parts"].append(extra)
            cases.append(answer)
        for index, answer in enumerate(cases):
            with self.subTest(index=index):
                self.assert_retained_failure(
                    self.invoke(str(index), answer=answer, audit=[])
                )

    def test_input_and_history_audit_rejects_transformations_or_hidden_steps(self):
        cases = []
        for key, value in (
            ("text", PROMPT.strip()),
            ("synthetic", True),
            ("ignored", True),
            ("messageID", "msg_other"),
        ):
            audit = history(response())
            audit[0]["parts"][0][key] = value
            cases.append(audit)
        for key, value in (
            ("id", "msg_other"),
            ("sessionID", "ses_other"),
            ("agent", "build"),
            ("system", "injected"),
        ):
            audit = history(response())
            audit[0]["info"][key] = value
            cases.append(audit)
        audit = history(response())
        audit[0]["info"]["format"]["retryCount"] = 2
        cases.append(audit)
        audit = history(response())
        audit[0]["parts"].append(
            {
                "type": "text",
                "text": SECRET,
                "id": "prt_extra_user",
                "sessionID": SESSION,
                "messageID": "msg_user",
            }
        )
        cases.append(audit)
        audit = history(response())
        audit.append(deepcopy(audit[1]))
        audit[-1]["info"]["id"] = "msg_earlier"
        audit[-1]["parts"][3]["tool"] = "bash"
        cases.append(audit)
        audit = history(response())
        audit[1]["parts"][3]["state"]["input"] = {"ok": False}
        cases.append(audit)
        cases.extend(([], {}, [None]))
        for index, audit in enumerate(cases):
            with self.subTest(index=index):
                self.assert_retained_failure(self.invoke(str(index), audit=audit))

    def test_timeout_aborts_then_terminates_without_retry(self):
        invoked = self.invoke(
            fail_at=("POST", "/session/" + SESSION + "/message"),
            error=TimeoutError(SECRET),
        )
        self.assert_retained_failure(invoked)
        result, _, _, calls = invoked[:4]
        self.assertTrue(result["timed_out"])
        self.assertEqual(result["exit_code"], 124)
        self.assertTrue(result["abort_succeeded"])
        self.assertEqual(result["prompt_posts"], 1)
        self.assertEqual(calls[-2][1], "/session/" + SESSION + "/abort")
        self.assertEqual(calls[-1][0], "terminate")
        invoked[6].assert_called_once()

    def test_audit_timeout_keeps_received_usage_but_not_a_completed_result(self):
        invoked = self.invoke(
            fail_at=("audit", "/event"),
            error=TimeoutError(SECRET),
        )
        self.assert_retained_failure(invoked)
        self.assertTrue(invoked[0]["timed_out"])
        self.assertEqual(invoked[0]["tokens"]["input"], 100)

    def test_http_failures_and_interrupts_do_not_escape_cleanup(self):
        for index, error in enumerate(
            (
                structured.TransportError("HTTP status 500"),
                OSError(SECRET),
                KeyboardInterrupt(),
            )
        ):
            invoked = self.invoke(
                str(index),
                fail_at=("POST", "/session/" + SESSION + "/message"),
                error=error,
            )
            self.assert_retained_failure(invoked)
            invoked[6].assert_called_once()
            self.assertTrue(invoked[0]["abort_attempted"])
        invoked = self.invoke(
            "abort",
            fail_at=("POST", "/session/" + SESSION + "/abort"),
            error=TimeoutError(),
        )
        invoked[6].assert_called_once()
        self.assertFalse(invoked[0]["abort_succeeded"])

    def test_startup_and_runtime_failures_never_issue_a_prompt(self):
        for index, error in enumerate(
            (TimeoutError(), structured.TransportError("Expected OpenCode 1.18.31"))
        ):
            invoked = self.invoke(str(index), startup_error=error)
            self.assert_retained_failure(invoked)
            self.assertEqual(invoked[0]["prompt_posts"], 0)
            self.assertFalse(invoked[0]["abort_attempted"])
            invoked[6].assert_called_once()
        invoked = self.invoke("runtime", runtime_error=ValueError(SECRET))
        self.assert_retained_failure(invoked)
        invoked[5].assert_not_called()
        invoked[6].assert_not_called()

    def test_existing_folder_is_never_overwritten_or_retried(self):
        invoked = self.invoke()
        before = {p.name: p.read_bytes() for p in invoked[2].iterdir()}
        with self.assertRaises(FileExistsError):
            structured.call_structured(invoked[2], "replacement", "replacement", SCHEMA)
        self.assertEqual({p.name: p.read_bytes() for p in invoked[2].iterdir()}, before)

    def test_each_call_gets_a_new_runtime_server_and_session(self):
        first = self.invoke("first")
        second = self.invoke("second")
        for invoked in (first, second):
            invoked[4].assert_called_once()
            invoked[5].assert_called_once()
            self.assertEqual(invoked[3][0][1], "/session")


class HttpAndLifecycleTests(OfflineTestCase):
    def test_sse_subscribes_before_prompt_and_audits_without_retaining_reasoning(self):
        lines = queue.Queue()
        connection = Mock()
        stream = Mock(status=200)
        stream.readline.side_effect = lambda limit: lines.get(timeout=5)
        connection.getresponse.return_value = stream
        connection.sock.shutdown.side_effect = lambda how: lines.put(b"")

        def send(event):
            # Exercise multiline data, CRLF, event names, and comment heartbeats.
            lines.put(b": heartbeat\r\n")
            lines.put(b"event: message\r\n")
            for line in json.dumps(event, indent=2).encode().splitlines():
                lines.put(b"data: " + line + b"\r\n")
            lines.put(b"\r\n")

        send({"type": "server.connected", "properties": {}})
        audit = INPUT_AUDIT(
            45678,
            SESSION,
            PROMPT,
            MODEL,
            "high",
            SCHEMA,
            structured.time.monotonic() + 5,
        )
        answer = response()
        with patch.object(
            structured.http.client, "HTTPConnection", return_value=connection
        ):
            with audit:
                self.assertTrue(audit.connected)
                connection.request.assert_called_once_with(
                    "GET", "/event", headers={"Accept": "text/event-stream"}
                )
                for item in history(answer):
                    info = deepcopy(item["info"])
                    if info["role"] == "assistant":
                        del info["time"]["completed"]
                    send({"type": "message.updated", "properties": {"info": info}})
                    for part in item["parts"]:
                        # Duplicate snapshots must not invent extra tool calls.
                        for _ in range(2):
                            send(
                                {
                                    "type": "message.part.updated",
                                    "properties": {"part": part},
                                }
                            )
                send(
                    {"type": "message.updated", "properties": {"info": answer["info"]}}
                )
                self.assertEqual(audit.finish(answer), (True, True))
                retained = [
                    audit.users,
                    audit.user_parts,
                    audit.tools,
                    list(audit.assistants),
                ]
                self.assertNotIn(SECRET, json.dumps(retained))
                self.assertNotIn(PROMPT, json.dumps(retained))
        self.assertFalse(audit.reader.is_alive())
        connection.sock.shutdown.assert_called_once()
        connection.close.assert_called_once()

    def test_sse_missing_handshake_or_malformed_data_fails_closed(self):
        for content in (
            b"",
            b"data: not-json\n\n",
            b"data: []\n\n",
            b'data: {"type":"server.connected"}\n\n',
        ):
            connection = Mock()
            stream = io.BytesIO(content)
            response = Mock(status=200)
            response.readline.side_effect = stream.readline
            connection.getresponse.return_value = response
            audit = INPUT_AUDIT(
                45678,
                SESSION,
                PROMPT,
                MODEL,
                "high",
                SCHEMA,
                structured.time.monotonic() + 5,
            )
            with patch.object(
                structured.http.client, "HTTPConnection", return_value=connection
            ):
                with self.assertRaises(structured.TransportError):
                    with audit:
                        self.fail("Bad audit stream accepted")
            connection.close.assert_called_once()

    def test_sse_error_response_is_not_read_or_saved(self):
        connection = Mock()
        response = Mock(status=401)
        connection.getresponse.return_value = response
        audit = INPUT_AUDIT(
            45678,
            SESSION,
            PROMPT,
            MODEL,
            "high",
            SCHEMA,
            structured.time.monotonic() + 5,
        )
        with patch.object(
            structured.http.client, "HTTPConnection", return_value=connection
        ):
            with self.assertRaisesRegex(structured.TransportError, "HTTP status 401"):
                with audit:
                    self.fail("Unauthorized audit stream accepted")
        response.read.assert_not_called()
        response.readline.assert_not_called()
        connection.close.assert_called_once()

    def test_http_is_direct_utf8_and_closes_connection(self):
        connection = Mock()
        response = Mock(status=200)
        response.read.return_value = b'{"ok":true}'
        connection.getresponse.return_value = response
        with patch.object(
            structured.http.client, "HTTPConnection", return_value=connection
        ) as factory:
            value = structured._request(45678, "POST", "/session", {"text": PROMPT}, 5)
        self.assertEqual(value, {"ok": True})
        factory.assert_called_once_with("127.0.0.1", 45678, timeout=5)
        self.assertEqual(
            json.loads(connection.request.call_args.kwargs["body"]), {"text": PROMPT}
        )
        self.assertIn("café".encode(), connection.request.call_args.kwargs["body"])
        connection.close.assert_called_once()

    def test_http_error_and_redirect_bodies_are_never_read(self):
        for status in (301, 401, 429, 500):
            connection = Mock()
            response = Mock(status=status, reason=SECRET)
            response.read.return_value = SECRET.encode()
            connection.getresponse.return_value = response
            with patch.object(
                structured.http.client, "HTTPConnection", return_value=connection
            ):
                with self.assertRaises(structured.TransportError) as error:
                    structured._request(45678, "POST", "/session", {}, 5)
            self.assertEqual(str(error.exception), "HTTP status " + str(status))
            response.read.assert_not_called()
            connection.request.assert_called_once()
            connection.close.assert_called_once()

    def test_malformed_nonfinite_duplicate_or_oversized_json_is_rejected(self):
        for raw in (
            b"{broken",
            b"\xff",
            b'{"x":NaN}',
            b'{"x":Infinity}',
            b'{"x":1e999}',
            b'{"x":"\\ud800"}',
            b'{"x":1,"x":2}',
            b" " * 101,
        ):
            connection = Mock()
            response = Mock(status=200)
            response.read.return_value = raw
            connection.getresponse.return_value = response
            with (
                patch.object(
                    structured.http.client, "HTTPConnection", return_value=connection
                ),
                patch.object(structured, "MAX_RESPONSE_BYTES", 100),
            ):
                with self.assertRaises(structured.TransportError):
                    structured._request(45678, "GET", "/global/health", timeout=5)
            connection.close.assert_called_once()

    def test_deadline_interrupts_socket_even_if_connection_drops_its_reference(self):
        connection = Mock()
        sock = connection.sock
        timer = Mock()

        def make_timer(timeout, interrupt):
            def getresponse():
                connection.sock = None
                interrupt()
                raise OSError(SECRET)

            connection.getresponse.side_effect = getresponse
            return timer

        with (
            patch.object(
                structured.http.client, "HTTPConnection", return_value=connection
            ),
            patch.object(structured.threading, "Timer", side_effect=make_timer),
        ):
            with self.assertRaises(TimeoutError):
                structured._request(45678, "POST", "/session", {}, 5)
        sock.shutdown.assert_called_once_with(structured.socket.SHUT_RDWR)
        timer.cancel.assert_called_once()
        timer.join.assert_called_once()
        connection.close.assert_called_once()

    def test_readiness_requires_own_banner_and_exact_version(self):
        for index, version in enumerate(("1.18.31", "1.18.32")):
            process = Mock()
            process.poll.return_value = None
            process.stdout = io.BytesIO(
                b"discarded startup log\nopencode server listening on http://127.0.0.1:45678\n"
            )
            with patch.object(
                structured,
                "_request",
                return_value={"healthy": True, "version": version},
            ) as request:
                if index == 0:
                    structured._wait_ready(
                        process, 45678, structured.time.monotonic() + 5
                    )
                else:
                    with self.assertRaisesRegex(
                        structured.TransportError, "Expected OpenCode"
                    ):
                        structured._wait_ready(
                            process, 45678, structured.time.monotonic() + 5
                        )
            self.assertEqual(request.call_args.args, (45678, "GET", "/global/health"))
        process = Mock()
        process.poll.return_value = 1
        process.stdout = io.BytesIO(
            b"opencode server listening on http://127.0.0.1:9999\n"
        )
        with patch.object(structured, "_request") as request:
            with self.assertRaisesRegex(structured.TransportError, "before readiness"):
                structured._wait_ready(process, 45678, structured.time.monotonic() + 5)
        request.assert_not_called()

    def test_cleanup_escalates_only_the_started_group_and_reaps(self):
        process = Mock(pid=24680, stdout=Mock())
        process.wait.side_effect = [subprocess.TimeoutExpired("opencode", 5), 0]
        with patch.object(structured.os, "killpg") as killpg:
            structured._terminate(process)
        self.assertEqual(
            killpg.call_args_list,
            [call(24680, signal.SIGTERM), call(24680, signal.SIGKILL)],
        )
        self.assertEqual(process.wait.call_count, 2)
        process.stdout.close.assert_called_once()

    def test_cleanup_tolerates_an_already_exited_group(self):
        process = Mock(pid=24680, stdout=Mock())
        with patch.object(
            structured.os, "killpg", side_effect=ProcessLookupError
        ) as killpg:
            structured._terminate(process)
        killpg.assert_called_once_with(24680, signal.SIGTERM)
        process.wait.assert_called_once()

    def test_free_port_binds_loopback_only_and_releases_reservation(self):
        sock = Mock()
        sock.getsockname.return_value = ("127.0.0.1", 45678)
        context = Mock()
        context.__enter__ = Mock(return_value=sock)
        context.__exit__ = Mock(return_value=False)
        with patch.object(structured.socket, "socket", return_value=context):
            self.assertEqual(structured._free_port(), 45678)
        sock.bind.assert_called_once_with(("127.0.0.1", 0))
        context.__exit__.assert_called_once()
