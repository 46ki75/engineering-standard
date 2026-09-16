"""Shared infrastructure for the isolated, real-tool formatting evaluation."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import time
import urllib.request
from pathlib import Path

COMMIT = "8af4521c5ff8ab4d254e0d956c0097274a0f37ae"
PLUGIN = "https://plugins.dprint.dev/exec-0.7.3.json"
HERE = Path(__file__).resolve().parent


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def download(url: str, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url, headers={"User-Agent": "dprint-formatting-evaluation/1.0"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        content = response.read()
    path.write_bytes(content)
    return digest(content)


class Harness:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.artifacts = self.root / "artifacts"
        self.tools = self.root / "environments/tools"
        self.baseline = self.root / "baseline"
        self.candidate = self.root / "candidate"
        marker = self.root / "evaluation.json"
        if not marker.is_file():
            raise ValueError("Not an initialized evaluation directory")
        self.manifest = json.loads(marker.read_text())
        self.env = self.manifest["environment"]
        self.sequence = 0

    def run(self, args, *, cwd=None, data=None, timeout=120, label="command", env=None):
        args = [str(a) for a in args]
        cwd = Path(cwd or self.candidate)
        self.sequence += 1
        name = f"{time.time_ns()}-{self.sequence}-{label}"
        log = self.artifacts / "commands" / name
        log.mkdir(parents=True)
        save(
            log / "request.json", {"args": args, "cwd": str(cwd), "timeout_s": timeout}
        )
        started = time.perf_counter()
        process = subprocess.Popen(
            args,
            cwd=cwd,
            env=env or self.env,
            stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        timed_out = False
        try:
            stdout, stderr = process.communicate(data, timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        except BaseException:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
            (log / "stdout").write_bytes(stdout)
            (log / "stderr").write_bytes(stderr)
            save(log / "interrupted.json", {"code": process.returncode})
            raise
        elapsed = (time.perf_counter() - started) * 1000
        (log / "stdout").write_bytes(stdout)
        (log / "stderr").write_bytes(stderr)
        result = {
            "args": args,
            "cwd": str(cwd),
            "code": process.returncode,
            "timeout": timed_out,
            "ms": elapsed,
            "stdin_sha256": digest(data) if data is not None else None,
            "stdout_sha256": digest(stdout),
            "stderr_sha256": digest(stderr),
            "log": str(log.relative_to(self.root)),
        }
        save(log / "result.json", result)
        return result, stdout, stderr

    def require(self, args, **kwargs):
        result, stdout, stderr = self.run(args, **kwargs)
        if result["code"] or result["timeout"]:
            raise RuntimeError(
                f"{args}: {result}\n{stderr.decode(errors='replace')[-4000:]}"
            )
        return stdout

    def dprint(self, verb, *args, **kwargs):
        return self.run([self.tools / "bin/dprint", verb, *args], **kwargs)

    def tracked(self, repo=None):
        return (
            self.require(["git", "ls-files", "-z"], cwd=repo or self.candidate)
            .decode()
            .split("\0")[:-1]
        )

    def snapshot(self, repo=None, paths=None):
        repo = repo or self.candidate
        return {
            p: digest((repo / p).read_bytes())
            for p in (paths if paths is not None else self.tracked(repo))
            if (repo / p).is_file()
        }

    def source_guard(self):
        source = Path(self.manifest["source"])
        current = self.require(
            ["git", "--no-optional-locks", "status", "--porcelain=v1"], cwd=source
        ).decode()
        return {
            "status_unchanged": current == self.manifest["source_status"],
            "head_unchanged": self.require(["git", "rev-parse", "HEAD"], cwd=source)
            .decode()
            .strip()
            == COMMIT,
        }

    def record_phase(self, name, result):
        result["source_guard"] = self.source_guard()
        result["harness_sha256"] = {
            str(p.relative_to(HERE)): digest(p.read_bytes())
            for p in sorted(HERE.iterdir())
            if p.suffix in (".py", ".lua", ".cjs")
        }
        destination = self.artifacts / f"{name}.json"
        if destination.exists():
            number = 1
            while (self.artifacts / f"{name}-attempt-{number}.json").exists():
                number += 1
            shutil.copy2(destination, self.artifacts / f"{name}-attempt-{number}.json")
        save(destination, result)
        summary = result.get("summary") or {
            k: v
            for k, v in result.items()
            if isinstance(v, (str, int, float, bool)) or (isinstance(v, list) and not v)
        }
        summary = dict(summary)
        summary["artifact"] = str(destination)
        print(json.dumps(summary, indent=2, ensure_ascii=False))


def initialize(root: Path, source: Path):
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("This pinned setup driver currently targets macOS arm64")
    root = root.resolve()
    source = source.resolve()
    if root.exists() or source == root or source in root.parents:
        raise ValueError("Use a new evaluation directory outside the source repository")
    binaries = {
        name: shutil.which(name)
        for name in ("dprint", "node", "rustup", "uv", "nvim", "code")
    }
    if any(value is None for value in binaries.values()):
        raise RuntimeError(f"Missing prerequisite: {binaries}")
    binaries = {name: str(value) for name, value in binaries.items()}
    node = subprocess.check_output(
        [binaries["node"], "-p", "process.execPath"], text=True
    ).strip()
    status = subprocess.check_output(
        ["git", "--no-optional-locks", "status", "--porcelain=v1"],
        cwd=source,
        text=True,
    )
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=source, text=True
    ).strip()
    if head != COMMIT:
        raise ValueError(f"Expected source commit {COMMIT}, found {head}")
    root.mkdir(parents=True)
    environment = root / "environments"
    bindir = environment / "tools/bin"
    bindir.mkdir(parents=True)
    for name in ("dprint", "rustup", "uv"):
        shutil.copy2(Path(binaries[name]).resolve(), bindir / name)
    (bindir / "node").symlink_to(node)
    for name in (
        "cargo",
        "rustfmt",
        "rustc",
        "rustdoc",
        "cargo-fmt",
        "cargo-clippy",
        "clippy-driver",
    ):
        (bindir / name).symlink_to("rustup")
    env = {
        "PATH": f"{bindir}:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(environment / "home"),
        "XDG_CONFIG_HOME": str(environment / "config"),
        "XDG_DATA_HOME": str(environment / "data"),
        "XDG_STATE_HOME": str(environment / "state"),
        "XDG_CACHE_HOME": str(environment / "cache"),
        "DPRINT_CACHE_DIR": str(environment / "dprint-cache"),
        "CARGO_HOME": str(environment / "cargo"),
        "RUSTUP_HOME": str(environment / "rustup"),
        "CARGO_TARGET_DIR": str(environment / "target"),
        "UV_CACHE_DIR": str(environment / "uv-cache"),
        "UV_PYTHON_INSTALL_DIR": str(environment / "python"),
        "UV_TOOL_DIR": str(environment / "uv-tools"),
        "UV_TOOL_BIN_DIR": str(bindir),
        "TMPDIR": str(environment / "tmp"),
        "LANG": "en_US.UTF-8",
        "LC_ALL": "en_US.UTF-8",
        "CI": "1",
        "NO_COLOR": "1",
        "CHECKPOINT_DISABLE": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    for key, value in env.items():
        if key.endswith("HOME") or key.endswith("DIR"):
            Path(value).mkdir(parents=True, exist_ok=True)
    manifest = {
        "source": str(source),
        "source_commit": COMMIT,
        "source_status": status,
        "environment": env,
        "host_binaries": binaries,
        "node_binary": node,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "created_unix": time.time(),
        "downloads": {},
    }
    save(root / "evaluation.json", manifest)
    return Harness(root)
