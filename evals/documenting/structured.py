"""Native structured judging through an isolated OpenCode 1.18.31 HTTP server.

The schema is passed to OpenCode's native StructuredOutput tool unchanged; this
adapter validates the completion protocol, not arbitrary JSON Schema semantics.
Callers should still apply domain validation (for example, validate_judgment).

Pinned source, all under https://github.com/anomalyco/opencode/blob/v1.18.31/:
  packages/opencode/src/session/prompt.ts (format, title, virtual tool, exit)
  packages/opencode/src/session/llm/request.ts (final permission filtering)
  packages/opencode/src/session/processor.ts (tool result and usage envelopes)
  packages/schema/src/v1/session.ts (wire schemas)
  packages/opencode/src/server/routes/instance/httpapi/{groups,handlers}/session.ts
  packages/opencode/src/server/routes/instance/httpapi/handlers/event.ts
  packages/opencode/src/cli/cmd/serve.ts (server-owned readiness announcement)
"""

from __future__ import annotations

import http.client
import json
import math
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import threading
import time

if __package__:
    from . import run
else:
    import run


AGENT = "documentation-eval"
TOOL = "StructuredOutput"
TOOL_OUTPUT = "Structured output captured successfully."
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
CLEANUP_TIMEOUT = 5
FINISHES = {"stop", "end_turn", "tool-calls"}
ERROR_NAMES = {
    "ProviderAuthError",
    "UnknownError",
    "MessageOutputLengthError",
    "MessageAbortedError",
    "StructuredOutputError",
    "ContextOverflowError",
    "ContentFilterError",
    "APIError",
}


class TransportError(Exception):
    """Only adapter-authored messages, never response bodies or exception text."""


def _json(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def _save(path, value):
    path.write_bytes(_json(value).encode("utf-8"))


def _reject_constant(value):
    raise ValueError("Nonfinite JSON number")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _same_json(first, second):
    # Python equality would treat true and 1 as interchangeable.
    return json.dumps(first, sort_keys=True, allow_nan=False) == json.dumps(
        second, sort_keys=True, allow_nan=False
    )


def _number(value):
    return (type(value) is int and value >= 0) or (
        type(value) is float and math.isfinite(value) and value >= 0
    )


def _identifier(value, prefix):
    return (
        isinstance(value, str)
        and re.fullmatch(prefix + r"_[A-Za-z0-9_-]{1,128}", value) is not None
    )


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError
    return remaining


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _request(port, method, path, payload=None, timeout: float = 600):
    """One proxy-free, redirect-free request with an overall wall-clock bound."""
    deadline = time.monotonic() + timeout
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    timer = None
    expired = threading.Event()
    try:
        connection.connect()
        sock = connection.sock

        def interrupt():
            expired.set()
            try:
                # Retain the socket: HTTPConnection can clear .sock when a
                # response announces Connection: close, while its body is read.
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

        timer = threading.Timer(_remaining(deadline), interrupt)
        timer.daemon = True
        timer.start()
        body = None if payload is None else _json(payload).encode("utf-8")
        connection.request(
            method,
            path,
            body=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        response = connection.getresponse()
        if not 200 <= response.status < 300:
            # Do not read, persist, or interpolate HTTP error bodies/headers.
            raise TransportError("HTTP status " + str(response.status))
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        _remaining(deadline)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise TransportError("HTTP response exceeds size limit")
        try:
            value = json.loads(
                raw.decode("utf-8"),
                parse_constant=_reject_constant,
                object_pairs_hook=_unique_object,
            )
            # parse_constant alone does not reject exponents overflowing float.
            json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
            return value
        except (ValueError, UnicodeError, RecursionError):
            raise TransportError("Invalid JSON response") from None
    except (OSError, http.client.HTTPException) as error:
        if expired.is_set() or isinstance(error, (TimeoutError, socket.timeout)):
            raise TimeoutError from None
        raise TransportError("HTTP connection failed") from None
    finally:
        if timer is not None:
            timer.cancel()
            timer.join()
        connection.close()


def _wait_ready(process, port, deadline):
    announced = threading.Event()
    banner = ("opencode server listening on http://127.0.0.1:" + str(port)).encode()

    def drain():
        # Logs are discarded in memory. An exact announcement from our child
        # prevents a port-allocation race from attaching to somebody else's server.
        try:
            for line in iter(lambda: process.stdout.readline(8192), b""):
                if line.rstrip(b"\r\n") == banner:
                    announced.set()
        except (OSError, ValueError):
            # Cleanup may close the pipe as this reader observes EOF.
            pass

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    while not announced.wait(min(0.05, _remaining(deadline))):
        if process.poll() is not None:
            raise TransportError("Server exited before readiness")
    if process.poll() is not None:
        raise TransportError("Server exited before readiness")
    health = _request(port, "GET", "/global/health", timeout=_remaining(deadline))
    if not isinstance(health, dict) or health.get("healthy") is not True:
        raise TransportError("Invalid server health response")
    if health.get("version") != "1.18.31":
        raise TransportError("Expected OpenCode 1.18.31")


def _terminate(process):
    """Signal only the process group created with start_new_session=True."""
    # Signal even if the leader exited: its descendants can still own the group.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        if sig == signal.SIGTERM:
            try:
                process.wait(timeout=CLEANUP_TIMEOUT)
            except subprocess.TimeoutExpired:
                continue
            # Reap any remaining descendants without touching unrelated groups.
            continue
    process.wait(timeout=CLEANUP_TIMEOUT)
    if process.stdout is not None:
        process.stdout.close()


def _time(value, keys):
    if not isinstance(value, dict):
        return {}
    return {key: value[key] for key in keys if _number(value.get(key))}


def _usage(value):
    if not isinstance(value, dict) or not _number(value.get("cost")):
        return None
    tokens = value.get("tokens")
    if not isinstance(tokens, dict) or not isinstance(tokens.get("cache"), dict):
        return None
    if not all(_number(tokens.get(key)) for key in ("input", "output", "reasoning")):
        return None
    if not all(_number(tokens["cache"].get(key)) for key in ("read", "write")):
        return None
    return {
        "cost": value["cost"],
        "tokens": {
            **{key: tokens[key] for key in ("input", "output", "reasoning")},
            "cache": {key: tokens["cache"][key] for key in ("read", "write")},
        },
    }


def _error(value):
    if not isinstance(value, dict):
        return {"name": "UnknownError"}
    name = value.get("name")
    result: dict = {
        "name": name
        if isinstance(name, str) and name in ERROR_NAMES
        else "UnknownError"
    }
    data = value.get("data")
    if isinstance(data, dict):
        result["data"] = {
            key: data[key]
            for key in ("statusCode", "retries")
            if _number(data.get(key))
        }
        if type(data.get("isRetryable")) is bool:
            result["data"]["isRetryable"] = data["isRetryable"]
    return result


def _parse_response(response, session_id, model, variant):
    """Return only whitelisted data; never retain reasoning/provider metadata."""
    safe = {"info": {}, "parts": []}
    events, failures = [], []
    value = None
    if not isinstance(response, dict) or not isinstance(response.get("info"), dict):
        return safe, events, value, ["Malformed assistant response"]
    info = response["info"]
    parts = response.get("parts")
    if not isinstance(parts, list):
        failures.append("Malformed assistant parts")
        parts = []
    provider, model_id = model.split("/", 1)
    for key, prefix in (("id", "msg"), ("sessionID", "ses"), ("parentID", "msg")):
        if _identifier(info.get(key), prefix):
            safe["info"][key] = info[key]
        else:
            failures.append("Invalid assistant identity")
    for key, expected in (
        ("role", "assistant"),
        ("sessionID", session_id),
        ("providerID", provider),
        ("modelID", model_id),
        ("agent", AGENT),
        ("variant", variant),
    ):
        if info.get(key) != expected:
            failures.append("Assistant " + key + " mismatch")
        elif expected is not None:
            safe["info"][key] = expected
    timing = _time(info.get("time"), ("created", "completed"))
    safe["info"]["time"] = timing
    if (
        set(timing) != {"created", "completed"}
        or timing["completed"] < timing["created"]
    ):
        failures.append("Incomplete assistant response")
    finish = info.get("finish")
    if isinstance(finish, str) and finish in FINISHES | {
        "length",
        "error",
        "content-filter",
        "unknown",
    }:
        safe["info"]["finish"] = finish
    if not isinstance(finish, str) or finish not in FINISHES:
        failures.append("Unexpected finish reason")
    if info.get("error") is not None:
        safe["info"]["error"] = _error(info["error"])
        failures.append("Assistant reported an error")
    usage = _usage(info)
    if usage is None:
        failures.append("Invalid assistant usage")
    else:
        safe["info"].update(usage)

    seen, tools, finishes = set(), [], []
    for part in parts:
        if not isinstance(part, dict):
            failures.append("Malformed response part")
            continue
        kind = part.get("type")
        if kind == "reasoning":
            continue
        if kind not in ("text", "tool", "step-start", "step-finish"):
            failures.append("Unsupported response part")
            continue
        if kind == "tool" and part.get("tool") != TOOL:
            failures.append("Unsupported tool call")
            continue
        if (
            not _identifier(part.get("id"), "prt")
            or part.get("id") in seen
            or part.get("sessionID") != session_id
            or part.get("messageID") != info.get("id")
        ):
            failures.append("Invalid or duplicate part identity")
            continue
        seen.add(part["id"])
        clean = {key: part[key] for key in ("id", "sessionID", "messageID", "type")}
        event_type = {
            "step-start": "step_start",
            "step-finish": "step_finish",
            "tool": "tool_use",
        }.get(kind, kind)
        if kind == "text":
            if not isinstance(part.get("text"), str):
                failures.append("Malformed text part")
                continue
            clean["text"] = part["text"]
            clean["time"] = _time(part.get("time"), ("start", "end"))
        elif kind == "tool":
            tools.append(part)
            state = part.get("state")
            if not isinstance(state, dict):
                failures.append("Malformed StructuredOutput state")
                continue
            status = state.get("status")
            clean.update({"tool": TOOL, "state": {}})
            if status in ("pending", "running", "completed", "error"):
                clean["state"]["status"] = status
            if isinstance(state.get("input"), dict):
                # This is the requested answer, not tool/provider transport metadata.
                clean["state"]["input"] = state["input"]
            clean["state"]["time"] = _time(state.get("time"), ("start", "end"))
            metadata = state.get("metadata")
            valid = isinstance(metadata, dict) and metadata.get("valid") is True
            clean["state"]["metadata"] = {"valid": valid}
            if state.get("output") == TOOL_OUTPUT:
                clean["state"]["output"] = TOOL_OUTPUT
            if state.get("error") is not None:
                clean["state"]["error"] = "StructuredOutput failed"
            if (
                status != "completed"
                or not isinstance(state.get("input"), dict)
                or not valid
                or state.get("output") != TOOL_OUTPUT
                or state.get("attachments")
                or state.get("error") is not None
                or set(clean["state"]["time"]) != {"start", "end"}
            ):
                failures.append("StructuredOutput did not complete successfully")
        elif kind == "step-finish":
            finishes.append(part)
            step_usage = _usage(part)
            reason = part.get("reason")
            if (
                step_usage is None
                or not isinstance(reason, str)
                or reason not in FINISHES
            ):
                failures.append("Invalid step usage or finish reason")
                continue
            clean.update(step_usage)
            clean["reason"] = reason
        safe["parts"].append(clean)
        events.append({"type": event_type, "sessionID": session_id, "part": clean})

    if len(tools) != 1:
        failures.append("Expected exactly one StructuredOutput call")
    else:
        state = tools[0].get("state")
        if isinstance(state, dict) and isinstance(state.get("input"), dict):
            value = info.get("structured", state["input"])
            if not isinstance(value, dict) or not _same_json(value, state["input"]):
                failures.append(
                    "StructuredOutput and assistant structured value disagree"
                )
    if len(finishes) > 1:
        failures.append("Unexpected model step count")
    elif not finishes and usage is not None and "completed" in timing:
        # Some HTTP exporters omit step parts. Use message usage ONCE, never in
        # addition to per-step usage. tokens.total overlaps the five buckets.
        events.append(
            {
                "type": "step_finish",
                "sessionID": session_id,
                "source": "message_info",
                "part": {
                    "type": "step-finish",
                    "reason": safe["info"].get("finish"),
                    **usage,
                },
            }
        )
    elif len(finishes) == 1 and usage is not None:
        if not _same_json(usage, _usage(finishes[0])):
            failures.append("Message and step usage disagree")
    return safe, events, value, failures


class _InputAudit:
    """Observe user input and message/tool identities without retaining history.

    Live 1.18.31 returns HTTP 400 when GET message(s) encodes a stored user
    json_schema Format class. /event uses JSON.stringify directly and registers
    its listener before server.connected. Subscribe before the sole prompt POST.
    """

    def __init__(self, port, session_id, prompt, model, variant, schema, deadline):
        self.port, self.session_id, self.prompt = port, session_id, prompt
        provider, model_id = model.split("/", 1)
        self.model = {"providerID": provider, "modelID": model_id}
        if variant is not None:
            self.model["variant"] = variant
        self.format = {"type": "json_schema", "schema": schema, "retryCount": 0}
        self.deadline = deadline
        self.condition = threading.Condition()
        self.connected = False
        self.failed = False
        self.users, self.user_parts, self.tools = {}, {}, {}
        self.assistants, self.completed = set(), set()
        self.connection = self.sock = self.reader = self.timer = None

    def _consume(self, event):
        if not isinstance(event, dict):
            raise ValueError
        if event.get("type") == "server.connected":
            self.connected = True
            return
        fields = event.get("properties", {})
        if not isinstance(fields, dict):
            raise ValueError
        if event.get("type") == "message.updated":
            info = fields.get("info", {})
            if not isinstance(info, dict) or info.get("sessionID") != self.session_id:
                return
            ident = info.get("id")
            if not _identifier(ident, "msg"):
                raise ValueError
            if info.get("role") == "user":
                self.users[ident] = (
                    self.users.get(ident, True)
                    and info.get("agent") == AGENT
                    and info.get("system") is None
                    and _same_json(info.get("model"), self.model)
                    and _same_json(info.get("format"), self.format)
                )
            elif info.get("role") == "assistant":
                self.assistants.add(ident)
                if "completed" in _time(info.get("time"), ("completed",)):
                    self.completed.add(ident)
        elif event.get("type") == "message.part.updated":
            part = fields.get("part", {})
            if not isinstance(part, dict) or part.get("sessionID") != self.session_id:
                return
            ident, message_id = part.get("id"), part.get("messageID")
            if not _identifier(ident, "prt") or not _identifier(message_id, "msg"):
                raise ValueError
            if message_id in self.users:
                parts = self.user_parts.setdefault(message_id, {})
                parts[ident] = (
                    parts.get(ident, True)
                    and part.get("type") == "text"
                    and part.get("text") == self.prompt
                    and not part.get("synthetic")
                    and not part.get("ignored")
                )
            elif part.get("type") == "tool":
                if part.get("tool") != TOOL:
                    raise ValueError
                self.tools[ident] = self._tool_signature(part)
        elif event.get("type") in ("message.removed", "message.part.removed"):
            if fields.get("sessionID") == self.session_id:
                raise ValueError

    @staticmethod
    def _tool_signature(part):
        state = part.get("state", {})
        if not isinstance(state, dict):
            raise ValueError
        return (
            state.get("status") == "completed",
            run.digest(json.dumps(state.get("input"), sort_keys=True, allow_nan=False)),
        )

    def _read(self, response):
        data = bytearray()
        try:
            while True:
                line = response.readline(MAX_RESPONSE_BYTES + 1)
                if not line or len(line) + len(data) > MAX_RESPONSE_BYTES:
                    raise ValueError
                if line.rstrip(b"\r\n") == b"":
                    if data:
                        event = json.loads(
                            data,
                            parse_constant=_reject_constant,
                            object_pairs_hook=_unique_object,
                        )
                        with self.condition:
                            self._consume(event)
                            self.condition.notify_all()
                        data.clear()
                elif line.startswith(b"data:"):
                    data.extend(line[5:].lstrip(b" ").rstrip(b"\r\n") + b"\n")
        except Exception:
            with self.condition:
                self.failed = True
                self.condition.notify_all()

    def _shutdown(self):
        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def __enter__(self):
        try:
            self.connection = http.client.HTTPConnection(
                "127.0.0.1", self.port, timeout=_remaining(self.deadline)
            )
            self.connection.connect()
            self.sock = self.connection.sock
            self.timer = threading.Timer(_remaining(self.deadline), self._shutdown)
            self.timer.daemon = True
            self.timer.start()
            self.connection.request(
                "GET", "/event", headers={"Accept": "text/event-stream"}
            )
            response = self.connection.getresponse()
            if response.status != 200:
                raise TransportError("Input audit HTTP status " + str(response.status))
            self.reader = threading.Thread(
                target=self._read, args=(response,), daemon=True
            )
            self.reader.start()
            with self.condition:
                while not self.connected:
                    self._wait()
                if self.failed:
                    raise TransportError("Input audit stream failed")
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def _wait(self):
        remaining = _remaining(self.deadline)
        if self.failed:
            raise TransportError("Input audit stream failed")
        self.condition.wait(remaining)

    def _input_matches(self, parent_id):
        parts = self.user_parts.get(parent_id, {})
        return (
            set(self.users) == {parent_id}
            and self.users.get(parent_id) is True
            and len(parts) == 1
            and all(parts.values())
        )

    def finish(self, response):
        info = response.get("info", {}) if isinstance(response, dict) else {}
        if not isinstance(info, dict) or not _identifier(info.get("id"), "msg"):
            return False, False
        with self.condition:
            while info["id"] not in self.completed:
                self._wait()
            _remaining(self.deadline)
            if self.failed:
                raise TransportError("Input audit stream failed")
            match = self._input_matches(info.get("parentID"))
            parts = response.get("parts", [])
            expected_tools = (
                {
                    part["id"]: self._tool_signature(part)
                    for part in parts
                    if isinstance(part, dict)
                    and part.get("type") == "tool"
                    and _identifier(part.get("id"), "prt")
                }
                if isinstance(parts, list)
                else {}
            )
            isolated = (
                set(self.users) == {info.get("parentID")}
                and self.assistants == {info["id"]}
                and self.tools == expected_tools
                and len(self.tools) == 1
                and all(signature[0] for signature in self.tools.values())
            )
            return bool(match), bool(isolated)

    def __exit__(self, *unused):
        self._shutdown()
        if self.timer is not None:
            self.timer.cancel()
            self.timer.join()
        if self.reader is not None:
            self.reader.join(timeout=CLEANUP_TIMEOUT)
        if self.connection is not None:
            self.connection.close()


def call_structured(
    folder, system, prompt, schema, model=run.JUDGE_MODEL, variant="high", timeout=600
):
    """Return (result metadata, structured dict or None), retaining failed trials.

    A fresh folder is required. Timeout includes startup, prompting, and audit;
    bounded abort/termination cleanup can extend it. exit_code describes the
    transport (0/1/124); server_exit_code records the intentionally stopped child.
    retryCount=0 disables structured repair, not OpenCode's internal provider
    retries. Only one prompt POST is issued. No raw server logs are saved.
    """
    if not isinstance(system, str) or not isinstance(prompt, str):
        raise ValueError("system and prompt must be strings")
    if not isinstance(schema, dict):
        raise ValueError("schema must be a JSON object")
    if not isinstance(model, str) or "/" not in model or not all(model.split("/", 1)):
        raise ValueError("model must be providerID/modelID")
    if variant is not None and not isinstance(variant, str):
        raise ValueError("variant must be a string or None")
    if not _number(timeout) or timeout == 0:
        raise ValueError("timeout must be finite and positive")
    # A JSON round trip prevents caller mutations during a request and rejects
    # non-JSON objects before starting a server or creating trial artifacts.
    schema = json.loads(_json(schema), parse_constant=_reject_constant)
    config = run.configuration(system, model)
    # prompt.ts adds this virtual final-response tool after ordinary tools;
    # llm/request.ts subsequently applies last-match permissions to ALL tools.
    permissions = {"*": "deny", TOOL: "allow"}
    config["permission"] = permissions.copy()
    config["agent"][AGENT]["permission"] = permissions.copy()
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "system.md").write_bytes(system.encode("utf-8"))
    (folder / "input.md").write_bytes(prompt.encode("utf-8"))
    _save(folder / "schema.json", schema)
    _save(folder / "config.json", config)

    start = time.monotonic()
    deadline = start + timeout
    process = None
    session_id = None
    port = None
    response = None
    safe, events, value, failures = {"info": {}, "parts": []}, [], None, []
    timed_out = False
    stage = "runtime"
    metadata = {
        "transport": "opencode-http",
        "input_audit_source": "event_stream",
        "server_started": False,
        "server_ready": False,
        "server_start_seconds": None,
        "server_exit_code": None,
        "prompt_posts": 0,
        "actual_input_match": False,
        "session_isolated": False,
        "abort_attempted": False,
        "abort_succeeded": False,
    }
    try:
        with run.isolated_runtime(config) as (executable, cwd, env):
            try:
                stage = "server startup"
                port = _free_port()
                process = subprocess.Popen(
                    [
                        executable,
                        "serve",
                        "--hostname",
                        "127.0.0.1",
                        "--port",
                        str(port),
                        "--pure",
                    ],
                    cwd=cwd,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                metadata["server_started"] = True
                _wait_ready(process, port, deadline)
                metadata["server_ready"] = True
                metadata["server_start_seconds"] = time.monotonic() - start
                stage = "session creation"
                session = _request(
                    port, "POST", "/session", {"title": AGENT}, _remaining(deadline)
                )
                if not isinstance(session, dict) or not _identifier(
                    session.get("id"), "ses"
                ):
                    raise TransportError("Invalid session identity")
                session_id = session["id"]
                if session.get("title") != AGENT or session.get("parentID"):
                    raise TransportError("Session title or isolation mismatch")
                provider, model_id = model.split("/", 1)
                payload = {
                    "model": {"providerID": provider, "modelID": model_id},
                    "agent": AGENT,
                    "parts": [{"type": "text", "text": prompt}],
                    "format": {
                        "type": "json_schema",
                        "schema": schema,
                        "retryCount": 0,
                    },
                }
                if variant is not None:
                    payload["variant"] = variant
                stage = "input audit subscription"
                with _InputAudit(
                    port, session_id, prompt, model, variant, schema, deadline
                ) as audit:
                    stage = "message request"
                    remaining = _remaining(deadline)
                    metadata["prompt_posts"] += 1
                    response = _request(
                        port,
                        "POST",
                        "/session/" + session_id + "/message",
                        payload,
                        remaining,
                    )
                    stage = "response validation"
                    safe, events, value, errors = _parse_response(
                        response, session_id, model, variant
                    )
                    failures.extend(errors)
                    stage = "input audit"
                    metadata["actual_input_match"], metadata["session_isolated"] = (
                        audit.finish(response)
                    )
                if not metadata["actual_input_match"]:
                    failures.append("Session input audit mismatch")
                if not metadata["session_isolated"]:
                    failures.append("Unexpected session history")
                if process.poll() is not None:
                    failures.append("Server exited unexpectedly")
                _remaining(deadline)
            finally:
                # This also runs for interrupts and failures while validating.
                # Abort before terminating so the provider request is canceled.
                if process is not None:
                    try:
                        if session_id is not None:
                            metadata["abort_attempted"] = True
                            try:
                                metadata["abort_succeeded"] = (
                                    _request(
                                        port,
                                        "POST",
                                        "/session/" + session_id + "/abort",
                                        timeout=CLEANUP_TIMEOUT,
                                    )
                                    is True
                                )
                            except (TransportError, OSError):
                                pass
                    finally:
                        try:
                            _terminate(process)
                        except (OSError, subprocess.TimeoutExpired):
                            failures.append("Server cleanup failed")
                        metadata["server_exit_code"] = process.returncode
    except TimeoutError:
        timed_out = True
        failures.append(stage + ": timeout")
    except TransportError as error:
        failures.append(stage + ": " + str(error))
    except (KeyboardInterrupt, SystemExit):
        failures.append(stage + ": interrupted")
    except Exception:
        # Runtime/OS/provider exceptions can embed environment values or bodies.
        failures.append(stage + ": local failure")

    metrics = run.event_metrics(events)
    metrics["provider_attempts"] = (
        "unavailable; OpenCode may retry internally; adapter does not retry"
    )
    if metrics["observed_model_steps"] != 1:
        failures.append("Expected one observed model step")
    if value is None:
        failures.append("Missing structured object")
    failures = list(dict.fromkeys(failures))
    value = None if failures else value
    text = "" if value is None else _json(value)
    _save(folder / "response.json", safe)
    (folder / "events.jsonl").write_bytes(
        "".join(
            json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n"
            for event in events
        ).encode("utf-8")
    )
    (folder / "output.md").write_bytes(text.encode("utf-8"))
    if value is not None:
        _save(folder / "structured.json", value)
    result = {
        "status": "failed" if failures else "completed",
        "failures": failures,
        "model": model,
        "variant": variant,
        "seconds": time.monotonic() - start,
        "exit_code": 124 if timed_out else (1 if failures else 0),
        "timed_out": timed_out,
        "session_ids": [session_id] if session_id else [],
        "system_sha256": run.digest(system),
        "input_sha256": run.digest(prompt),
        "schema_sha256": run.digest(_json(schema)),
        "output_sha256": run.digest(text),
        "output_words": len(text.split()),
        **metrics,
        **metadata,
    }
    _save(folder / "result.json", result)
    return result, value
