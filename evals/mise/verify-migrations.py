"""Exercise migrated task contracts in disposable repositories with fake tools.

Uses the sibling repositories by default. No deployment or project build is run.
Real tool installation and project checks are recorded separately in README.md.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib


STUB = r"""
import json
import os
from pathlib import Path
import sys

tool = Path(sys.argv[0]).name
with open(os.environ["PROBE_LOG"], "a") as log:
    log.write(json.dumps({
        "tool": tool,
        "args": sys.argv[1:],
        "cwd": str(Path.cwd()),
        "stage": os.environ.get("STAGE_NAME"),
        "vite_stage": os.environ.get("VITE_STAGE_NAME"),
        "tag": os.environ.get("TAG"),
    }) + "\n")
if os.environ.get("FAIL_TOOL") == tool:
    sys.exit(17)
if tool == "aws" and sys.argv[1:3] == ["sts", "get-caller-identity"]:
    print("123456789012")
elif tool == "aws" and sys.argv[1:3] == ["ecr", "get-login-password"]:
    print("fixture-password")
elif tool == "docker" and sys.argv[1:2] == ["login"]:
    sys.stdin.read()
"""


class Fixture:
    def __init__(self, source: Path, root: Path, mise: str):
        self.source = source
        self.root = (root / f"{source.name} with spaces").resolve()
        self.root.mkdir()
        self.mise = mise
        for name in ("mise.toml", "mise.lock", "package.json", "rust-toolchain.toml"):
            if (source / name).exists():
                shutil.copy2(source / name, self.root / name)
        shutil.copytree(source / ".mise", self.root / ".mise")
        config = tomllib.loads((self.root / "mise.toml").read_text())
        for task in config["tasks"].values():
            (self.root / task.get("dir", ".")).mkdir(parents=True, exist_ok=True)
        self.bin = self.root / "fake-bin"
        self.bin.mkdir()
        self.log = self.root / "commands.jsonl"
        for tool in ("cargo", "pnpm", "uv", "terraform", "aws", "docker", "rustup"):
            path = self.bin / tool
            path.write_text(f"#!{sys.executable}\n{STUB}")
            path.chmod(0o755)
        scripts = self.root / "packages/web-solid/scripts"
        if source.name in ("web", "internal"):
            scripts.mkdir(parents=True, exist_ok=True)
            for name in ("deploy-s3.sh", "deploy-lambda.sh", "invalidate.sh"):
                path = scripts / name
                path.write_text(f"#!{sys.executable}\n{STUB}")
                path.chmod(0o755)
        # Environment PATH entries must precede mise's installed tool paths.
        (self.root / "mise.local.toml").write_text(
            '[env]\n_.path = ["{{ config_root }}/fake-bin"]\n'
        )
        global_config = root / "empty-global.toml"
        global_config.touch()
        self.env = {
            **os.environ,
            "MISE_GLOBAL_CONFIG_FILE": str(global_config),
            "MISE_TRUSTED_CONFIG_PATHS": str(root),
            "MISE_NO_HOOKS": "1",
            "MISE_OFFLINE": "1",
            "MISE_AUTO_INSTALL": "0",
            "PROBE_LOG": str(self.log),
        }
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        build = source / "python/ag-ui-server/build.sh"
        if build.exists():
            target = self.root / "python/ag-ui-server/build.sh"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(build, target)

    def run(self, task: str, *args: str, cwd: str = ".", fail: str = ""):
        self.log.write_text("")
        result = subprocess.run(
            [self.mise, "run", task, *args],
            cwd=self.root / cwd,
            env={**self.env, "FAIL_TOOL": fail},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
        events = [json.loads(line) for line in self.log.read_text().splitlines()]
        return result, events


def require(condition: bool, detail: object):
    if not condition:
        raise AssertionError(detail)


def verify_deploy(fixture: Fixture, task: str, directory: str, binary: str, name: str):
    result, events = fixture.run(task, "stg", cwd=directory)
    require(result.returncode == 0, result.stdout)
    require(len(events) == 2, events)
    require(events[0]["args"][:2] == ["lambda", "build"], events)
    require(
        events[1]["args"] == ["lambda", "deploy", "--binary-name", binary, name],
        events,
    )
    require(all(e["cwd"] == str(fixture.root / directory) for e in events), events)
    result, events = fixture.run(task, "stg", fail="cargo")
    require(result.returncode != 0 and len(events) == 1, (result.stdout, events))
    for arguments in ((), ("invalid-stage",)):
        result, events = fixture.run(task, *arguments)
        require(result.returncode != 0 and not events, (result.stdout, events))


def verify_selection(fixture: Fixture, directory: str):
    for task in ("fmt", "fmt-check"):
        result, events = fixture.run(
            task, "--file", "path with spaces.ts", "--file", "other.ts", cwd=directory
        )
        require(result.returncode == 0 and len(events) == 1, result.stdout)
        require(
            events[0]["args"]
            == [
                "exec",
                "lefthook",
                "run",
                task,
                "--no-auto-install",
                "--file",
                "path with spaces.ts",
                "--file",
                "other.ts",
            ],
            events,
        )
        require(events[0]["cwd"] == str(fixture.root), events)
    result, _ = fixture.run("fmt-check", fail="pnpm")
    require(result.returncode != 0, result.stdout)


def verify_hook(fixture: Fixture):
    shutil.copy2(fixture.source / "lefthook.yml", fixture.root / "lefthook.yml")
    subprocess.run(
        [
            fixture.mise,
            "exec",
            "--",
            str(fixture.source / "node_modules/.bin/lefthook"),
            "install",
            "pre-commit",
        ],
        cwd=fixture.root,
        env=fixture.env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    fixture.log.write_text("")
    env = {
        key: value
        for key, value in fixture.env.items()
        if key.startswith("MISE_") or key in ("HOME", "PROBE_LOG")
    }
    env["PATH"] = f"{Path(fixture.mise).parent}:/usr/bin:/bin"
    result = subprocess.run(
        ["git", "hook", "run", "pre-commit"],
        cwd=fixture.root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    require(result.returncode == 0, result.stdout)
    events = [json.loads(line) for line in fixture.log.read_text().splitlines()]
    require(len(events) == 1 and events[0]["tool"] == "pnpm", events)
    require(events[0]["args"][:4] == ["exec", "lefthook", "run", "pre-commit"], events)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repositories-root", type=Path, default=Path(__file__).resolve().parents[3]
    )
    parser.add_argument("--temp-dir", type=Path)
    args = parser.parse_args()
    mise = shutil.which("mise")
    if mise is None:
        raise RuntimeError("mise must be on PATH")
    with tempfile.TemporaryDirectory(
        dir=args.temp_dir, prefix="mise-migration-"
    ) as tmp:
        fixtures = {
            name: Fixture(args.repositories_root / name, Path(tmp), mise)
            for name in ("elmethis", "web", "internal")
        }
        web, internal = fixtures["web"], fixtures["internal"]
        for fixture, task, directory, binary, name in (
            (
                web,
                "http-api:deploy",
                "crates/web-lambda-http-api",
                "web-lambda-http-api",
                "stg-46ki75-web-lambda-function-http_api",
            ),
            (
                web,
                "http-api:deploy-publisher",
                "crates/web-lambda-http-api",
                "web-lambda-blog-publisher",
                "stg-46ki75-web-lambda-function-blog_publisher",
            ),
            (
                web,
                "logs-reporter:deploy",
                "crates/web-lambda-logs-reporter",
                "web-lambda-logs-reporter",
                "stg-46ki75-web-lambda-function-reporter",
            ),
            (
                web,
                "legacy:http-api-old:deploy",
                "crates/http-api-old",
                "http-api",
                "stg-46ki75-web-lambda-function-http_api",
            ),
            (
                internal,
                "http-api:deploy",
                "crates/http-api",
                "http-api",
                "stg-46ki75-internal-lambda-function-http-api",
            ),
            (
                internal,
                "logs-reporter:deploy",
                "crates/logs-reporter",
                "logs-reporter",
                "stg-46ki75-internal-lambda-function-reporter",
            ),
        ):
            verify_deploy(fixture, task, directory, binary, name)
        print(
            "PASS: six Lambda deploy tasks preserve order, CWD, arguments, and failures"
        )

        result, events = web.run("http-api:invoke-publisher", "prod")
        require(result.returncode == 0 and len(events) == 1, result.stdout)
        require(
            events[0]["args"][-5:]
            == ["--cli-read-timeout", "900", "--payload", "{}", "/dev/stdout"],
            events,
        )
        require(
            events[0]["args"][3] == "prod-46ki75-web-lambda-function-blog_publisher",
            events,
        )
        print("PASS: publisher invocation preserves timeout, payload, and stage")

        for fixture, expected, stage_key in (
            (
                web,
                ["pnpm", "deploy-s3.sh", "deploy-lambda.sh", "invalidate.sh"],
                "stage",
            ),
            (internal, ["pnpm", "deploy-s3.sh", "invalidate.sh"], "vite_stage"),
        ):
            result, events = fixture.run("web:deploy", "stg")
            require(result.returncode == 0, result.stdout)
            require([e["tool"] for e in events] == expected, events)
            require(all(e[stage_key] == "stg" for e in events), events)
            require(
                all(
                    Path(e["cwd"]) == fixture.root / "packages/web-solid"
                    for e in events
                ),
                events,
            )
            result, events = fixture.run("web:deploy", "stg", fail="pnpm")
            require(result.returncode != 0 and len(events) == 1, result.stdout)
        print("PASS: frontend build/deploy/invalidation order and stage environment")

        for tag in ("release 1; not-a-command", ""):
            result, events = internal.run(
                "ag-ui-server:deploy",
                "dev",
                *([tag] if tag else []),
                cwd="python/ag-ui-server",
            )
            require(result.returncode == 0, result.stdout)
            require(events[0]["tool"] == "uv", events)
            actual_tag = events[0]["tag"]
            require(
                actual_tag == tag
                if tag
                else re.fullmatch(r"\d{8}-\d{6}", actual_tag) is not None,
                events,
            )
            build = next(
                e
                for e in events
                if e["tool"] == "docker" and e["args"][:2] == ["buildx", "build"]
            )
            require(
                f"123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/dev/ag-ui-server:{actual_tag}"
                in build["args"],
                build,
            )
            require(
                events[-2]["args"]
                == ["-chdir=terraform", "workspace", "select", "dev"],
                events,
            )
            require(events[-1]["args"] == ["-chdir=terraform", "apply"], events)
        for failing_tool in ("uv", "docker", "terraform"):
            result, events = internal.run(
                "ag-ui-server:deploy", "dev", fail=failing_tool
            )
            require(result.returncode != 0, result.stdout)
            require(
                not any(e["args"] == ["-chdir=terraform", "apply"] for e in events),
                events,
            )
        print(
            "PASS: AgentCore stage/tag forwarding, timestamp default, and failure ordering"
        )

        for task, directory in (
            ("rust:coverage:ci", "."),
            ("http-api:coverage:ci", "crates/http-api"),
        ):
            result, events = internal.run(task)
            require(result.returncode == 0 and len(events) == 2, result.stdout)
            require("--no-report" in events[0]["args"], events)
            require(
                events[1]["args"]
                == ["llvm-cov", "report", "--lcov", "--output-path", "lcov.info"],
                events,
            )
            require(
                all(Path(e["cwd"]) == internal.root / directory for e in events), events
            )
        result, _ = internal.run("rust:coverage")
        require(result.returncode == 0, result.stdout)
        print(
            "PASS: coverage instrumentation precedes reports with the original output scope"
        )

        verify_selection(fixtures["elmethis"], "packages/core")
        verify_selection(internal, "crates/http-api")
        print(
            "PASS: repeated file arguments, spaces, root-relative selection, and failure propagation"
        )
        verify_hook(fixtures["elmethis"])
        verify_hook(internal)
        print("PASS: generated Git hooks launch through mise without shell activation")


if __name__ == "__main__":
    main()
