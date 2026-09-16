#!/usr/bin/env python3
"""Evaluate the Lefthook guide in isolated repositories using real native tools."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import time
import tomllib
import traceback


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1]
SKIP_DIRS = {".git", "node_modules", ".venv", ".ruff_cache", "__pycache__", "target"}
GUIDE = "skills/engineering-standard/references/lefthook/README.md"
WEB = "packages/web/src/top.ts"
ODD = "packages/web/src/new ü & ' file.ts"
DIRTY_PY = "value=  1\n"
DIRTY_TS = 'export const value={message:"hello"};\n'


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(value).hexdigest()


def write(root, relative, content):
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")


def file_hashes(root):
    result = {}
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(name for name in dirs if name not in SKIP_DIRS)
        for name in sorted(files):
            path = Path(directory) / name
            if path.is_file():
                result[str(path.relative_to(root))] = digest(path.read_bytes())
    return result


class Evaluation:
    def __init__(self, source, scratch):
        self.source = source
        self.scratch = scratch
        self.root = Path(tempfile.mkdtemp(prefix="lefthook-guide-", dir=scratch))
        self.repo = self.root / "repository with spaces"
        self.commands = []
        self.cases = []
        self.active = {"name": "setup", "assertions": []}
        self.env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("GIT_", "LEFTHOOK", "UV_"))
            and key not in {"CI", "VIRTUAL_ENV", "PYTHONPATH", "CLICOLOR_FORCE"}
        }
        self.env.update(
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_TERMINAL_PROMPT="0",
            GIT_AUTHOR_NAME="Lefthook Evaluation",
            GIT_AUTHOR_EMAIL="evaluation@example.invalid",
            GIT_COMMITTER_NAME="Lefthook Evaluation",
            GIT_COMMITTER_EMAIL="evaluation@example.invalid",
            NO_COLOR="1",
            # tsx opens a Unix socket under TMPDIR; the longer run directory
            # exceeded macOS's socket-path limit in the calibration run.
            TMPDIR=str(scratch),
            UV_CACHE_DIR=str(self.root / "uv-cache"),
            PYTHONDONTWRITEBYTECODE="1",
        )
        self.config = (HERE / "guide-case.yml").read_text()
        self.tools = tomllib.loads((source / "mise.toml").read_text())["tools"]
        self.manifest = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "platform": platform.platform(),
            "architecture": platform.machine(),
            "scope": "guide-derived synthetic adoption and committed-repository regression",
            "inputs": {},
            "tools": {},
        }

    def portable(self, text):
        return (
            text.replace(str(self.root), "$RUN")
            .replace(str(self.source), "$SOURCE")
            .replace(str(self.scratch), "$SCRATCH")
            .replace(str(Path.home()), "$HOME")
        )

    def run(self, args, *, cwd=None, env=None, ok=None, timeout=300):
        cwd = cwd or self.repo
        started = time.monotonic()
        result = subprocess.run(
            args,
            cwd=cwd,
            env={**self.env, **(env or {})},
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        self.commands.append(
            {
                "case": self.active["name"],
                "cwd": self.portable(str(cwd)),
                "argv": [self.portable(str(arg)) for arg in args],
                "env_overrides": env or {},
                "exit": result.returncode,
                "seconds": round(time.monotonic() - started, 4),
                "stdout": self.portable(result.stdout),
                "stderr": self.portable(result.stderr),
            }
        )
        write(
            self.root,
            f"logs/{len(self.commands) - 1:04d}.txt",
            self.portable(result.stdout + result.stderr),
        )
        if ok is not None:
            self.require(
                (result.returncode == 0) == ok,
                f"Expected {'success' if ok else 'failure'}: {' '.join(args)}",
                {"exit": result.returncode, "command": len(self.commands) - 1},
            )
        return result

    def git(self, *args, cwd=None, ok=True):
        return self.run(["git", *args], cwd=cwd, ok=ok)

    def require(self, condition, description, evidence=None):
        self.active["assertions"].append(
            {
                "description": description,
                "passed": bool(condition),
                "evidence": evidence,
            }
        )
        if not condition:
            raise AssertionError(description)

    def state(self, repo=None):
        repo = repo or self.repo
        return {
            "files": file_hashes(repo),
            "index": digest(self.git("diff", "--cached", "--binary", cwd=repo).stdout),
            "status": self.git("status", "--porcelain=v1", "-z", cwd=repo).stdout,
            "head": self.git("rev-parse", "HEAD", cwd=repo).stdout.strip(),
        }

    def preserved(self, before, after, description):
        changed = sorted(
            name
            for name in before["files"].keys() | after["files"].keys()
            if before["files"].get(name) != after["files"].get(name)
        )
        self.require(
            before == after,
            description,
            {
                "before": digest(before),
                "after": digest(after),
                "changed_files": changed,
            },
        )

    def hook(self, hook, *args, ok=True, env=None, readonly=None, cwd=None):
        repo = self.repo
        readonly = (
            hook in {"lint", "fmt-check", "check"} if readonly is None else readonly
        )
        before = self.state(repo) if readonly else None
        command = len(self.commands)
        result = self.run(
            ["pnpm", "exec", "lefthook", "run", hook, "--no-auto-install", *args],
            cwd=cwd,
            env=env,
            ok=None,
        )
        if readonly:
            self.preserved(
                before, self.state(repo), f"{hook} preserves source and index"
            )
        self.require(
            (result.returncode == 0) == ok,
            f"{hook} exits with {'success' if ok else 'failure'}",
            {"exit": result.returncode, "command": command},
        )
        return result

    def install(self, repo):
        self.run(
            ["pnpm", "install", "--frozen-lockfile", "--ignore-scripts"],
            cwd=repo,
            ok=True,
        )
        if (repo / "mise.lock").exists():
            self.run(
                ["mise", "exec", "--", "uv", "sync", "--locked"],
                cwd=repo,
                env={"MISE_TRUSTED_CONFIG_PATHS": str(repo)},
                ok=True,
            )
        else:
            self.run(["uv", "sync", "--locked"], cwd=repo, ok=True)

    def freeze(self):
        self.before_source = self.state(self.source)
        self.manifest["source_head"] = self.before_source["head"]
        for relative in (
            GUIDE,
            "skills/engineering-standard/references/lefthook/lefthook.example.yml",
            "skills/engineering-standard/references/formatting/README.md",
            "lefthook.yml",
            "mise.toml",
            "mise.lock",
            "package.json",
            "pnpm-lock.yaml",
            "pyproject.toml",
            "uv.lock",
            "evals/lefthook/guide-case.yml",
            "evals/lefthook/evaluate-guide.py",
        ):
            data = (self.source / relative).read_bytes()
            target = self.root / "inputs" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            self.manifest["inputs"][relative] = digest(data)
        for name, args, expected in (
            ("node", ["node", "--version"], "v24.20.0"),
            ("pnpm", ["pnpm", "--version"], "12.4.1"),
            ("uv", ["uv", "--version"], "uv 0.12.9"),
            ("python", ["python", "--version"], f"Python {self.tools['python']}"),
            ("cargo", ["cargo", "--version"], "cargo 1.98.0"),
            ("rustc", ["rustc", "--version"], "rustc 1.98.0"),
        ):
            version = self.run(args, cwd=self.source, ok=True).stdout.strip()
            self.require(version.startswith(expected), f"Pinned {name}: {expected}")
            self.manifest["tools"][name] = version

    def setup(self):
        self.repo.mkdir()
        for name in (
            "package.json",
            "pnpm-lock.yaml",
            "pnpm-workspace.yaml",
            "pyproject.toml",
            "uv.lock",
        ):
            shutil.copy2(self.source / name, self.repo / name)
        # This standalone Lefthook fixture selects the source project's Python
        # without inheriting its task graph or duplicating its version pin.
        write(self.repo, ".python-version", self.tools["python"] + "\n")
        package = json.loads((self.repo / "package.json").read_text())
        package["scripts"] = {
            name: f"lefthook run {name}"
            for name in ("fmt", "fmt-check", "lint", "check")
        }
        write(self.repo, "package.json", json.dumps(package, indent=2) + "\n")
        files = {
            ".gitignore": "node_modules/\n.venv/\n.ruff_cache/\ntarget/\nignored/\n",
            "lefthook.yml": self.config,
            "root.py": "value = 1\n",
            "python/nested.py": "value = 2\n",
            "README.md": "# Fixture\n",
            "docs/nested.md": "# Nested\n",
            "docs/frozen/bad.md": "-   preserved\n",
            "generated/bad.py": "deliberately invalid !!!\n",
            "ignored/bad.py": "deliberately invalid !!!\n",
            ".prettierrc.json": '{"singleQuote": false}\n',
            "packages/web/package.json": '{"name":"evaluation-web","private":true}\n',
            "packages/web/.prettierrc.json": '{"singleQuote": true}\n',
            "packages/web/tsconfig.json": '{"compilerOptions":{"strict":true,"noEmit":true,"types":[]},"include":["src/**/*.ts"],"exclude":["src/generated"]}\n',
            WEB: "export const value = { message: 'hello' };\n",
            "packages/web/src/nested/deep.ts": "export const nested = 1;\n",
            "packages/web/src/generated/bad.ts": "deliberately invalid !!!\n",
            "model.mjs": "export const value = 1;\n",
            "behavior.test.mjs": 'import test from "node:test";\nimport assert from "node:assert/strict";\nimport { value } from "./model.mjs";\ntest("model", () => assert.equal(value, 1));\n',
            "Cargo.toml": '[workspace]\nmembers = ["crates/a", "crates/b"]\nresolver = "3"\n',
        }
        for crate in ("a", "b"):
            files[f"crates/{crate}/Cargo.toml"] = (
                f'[package]\nname = "probe-{crate}"\nversion = "0.1.0"\nedition = "2024"\n'
            )
            files[f"crates/{crate}/src/lib.rs"] = "pub fn value() -> u8 {\n    1\n}\n"
        for name, content in files.items():
            write(self.repo, name, content)
        self.git("init", "--quiet")
        self.install(self.repo)
        self.run(["cargo", "generate-lockfile", "--offline"], ok=True)
        for name, args, expected in (
            ("lefthook", ["pnpm", "exec", "lefthook", "version"], "2.1.14"),
            ("prettier", ["pnpm", "exec", "prettier", "--version"], "3.6.2"),
            (
                "ruff",
                ["uv", "run", "--locked", "--no-sync", "ruff", "--version"],
                "ruff 0.15.19",
            ),
            ("typescript", ["pnpm", "exec", "tsc", "--version"], "Version 7.0.2"),
            (
                "python",
                ["uv", "run", "--locked", "--no-sync", "python", "--version"],
                "Python 3.12.",
            ),
        ):
            version = self.run(args, ok=True).stdout.strip()
            self.require(version.startswith(expected), f"Pinned {name}: {expected}")
            self.manifest["tools"][name] = version
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "test: initialize evaluation fixture")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.manifest["fixture_files"] = file_hashes(self.repo)
        self.cases.append({**self.active, "passed": True})

    def case(self, name, function, *, reset=True):
        self.active = {"name": name, "assertions": []}
        start = len(self.commands)
        try:
            if reset:
                self.git("reset", "--hard", self.base)
                self.git("clean", "-fd")
            function()
            self.active["passed"] = True
        except Exception as error:
            self.active["passed"] = False
            self.active["error"] = self.portable(str(error))
        self.active["commands"] = list(range(start, len(self.commands)))
        self.cases.append(self.active)
        print(f"{'PASS' if self.active['passed'] else 'FAIL'} {name}", flush=True)
        self.save()

    def configure(self, text):
        write(self.repo, "lefthook.yml", text)

    def validate(self):
        self.run(["pnpm", "exec", "lefthook", "validate"], ok=True)
        dumped = json.loads(
            self.run(
                ["pnpm", "exec", "lefthook", "dump", "--format", "json"], ok=True
            ).stdout
        )
        self.require(
            "fmt-check" in dumped, "Resolved configuration contains custom hooks"
        )
        write(self.root, "resolved.json", json.dumps(dumped, indent=2) + "\n")
        self.hook("check")

    def cycle(self, path, content, direct):
        write(self.repo, path, content)
        self.hook("fmt-check", "--file", path, ok=False)
        self.hook("fmt", "--file", path)
        formatted = (self.repo / path).read_bytes()
        self.require(
            formatted != content.encode(), "Formatter changes deliberately dirty input"
        )
        self.hook("fmt-check", "--file", path)
        self.hook("fmt", "--file", path)
        self.require(
            (self.repo / path).read_bytes() == formatted, "Second format is byte-stable"
        )
        write(self.repo, path, content)
        cwd, args = direct
        self.run(args, cwd=self.repo / cwd, ok=True)
        actual = (self.repo / path).read_bytes()
        self.require(
            actual == formatted,
            "Direct native output equals delegated output",
            {"direct": digest(actual), "delegated": digest(formatted)},
        )

    def selections(self, matcher):
        config = self.config
        if matcher == "doublestar":
            config = config.replace("glob_matcher: gobwas", "glob_matcher: doublestar")
            config = config.replace('["*.py", "**/*.py"]', '"**/*.py"').replace(
                '["*.md", "**/*.md"]', '"**/*.md"'
            )
            config = config.replace(
                '["packages/web/src/*.ts", "packages/web/src/**/*.ts"]',
                '"packages/web/src/**/*.ts"',
            )
        self.configure(config)
        for path, content in (
            ("root.py", DIRTY_PY),
            ("python/nested.py", DIRTY_PY),
            (WEB, DIRTY_TS),
            ("packages/web/src/nested/deep.ts", DIRTY_TS),
            ("README.md", "-   item\n"),
            ("docs/nested.md", "-   item\n"),
        ):
            self.cycle(
                path,
                content,
                (".", ["uv", "run", "--locked", "--no-sync", "ruff", "format", path])
                if path.endswith(".py")
                else (
                    (
                        "packages/web",
                        [
                            "pnpm",
                            "exec",
                            "prettier",
                            "--write",
                            str(Path(path).relative_to("packages/web")),
                        ],
                    )
                    if path.endswith(".ts")
                    else (".", ["pnpm", "exec", "prettier", "--write", path])
                ),
            )

    def defaults(self, args):
        write(self.repo, "untracked.py", DIRTY_PY)
        self.hook("fmt-check", *args)
        write(self.repo, "root.py", DIRTY_PY)
        self.hook("fmt-check", *args, ok=False)
        self.hook("fmt", *args)
        self.require(
            (self.repo / "root.py").read_text() == "value = 1\n",
            "Tracked dirty file is formatted",
        )
        self.require(
            (self.repo / "untracked.py").read_text() == DIRTY_PY,
            "Default scope excludes untracked file",
        )

    def explicit(self):
        odd_py = "python/new ü & ' file.py"
        write(self.repo, odd_py, DIRTY_PY)
        write(self.repo, ODD, DIRTY_TS)
        write(self.repo, "root.py", DIRTY_PY)
        args = ("--file", odd_py, "--file", ODD)
        self.hook("fmt-check", *args, ok=False)
        self.hook("fmt", *args)
        self.hook("fmt-check", *args)
        self.require(
            (self.repo / odd_py).read_text() == "value = 1\n",
            "Unusual Python path is selected",
        )
        self.require(
            (self.repo / ODD).read_text()
            == "export const value = { message: 'hello' };\n",
            "Package-local configuration applies to unusual TypeScript path",
        )
        self.require(
            (self.repo / "root.py").read_text() == DIRTY_PY,
            "Repeated --file excludes unrelated tracked input",
        )
        self.git("add", "--", odd_py, ODD)
        self.hook("fmt", "--all-files")
        self.hook("fmt-check", "--all-files")

    def matcher_depth(self):
        config = self.config.replace('["*.py", "**/*.py"]', '"**/*.py"')
        self.configure(config)
        write(self.repo, "root.py", DIRTY_PY)
        result = self.hook("fmt-check", "--file", "root.py")
        self.require(
            "python (skip)" in result.stdout,
            "Default **/*.py does not cover root-level file",
        )
        write(self.repo, "python/nested.py", DIRTY_PY)
        self.hook("fmt-check", "--file", "python/nested.py", ok=False)
        self.configure(
            config.replace("glob_matcher: gobwas", "glob_matcher: doublestar")
        )
        self.hook("fmt-check", "--file", "root.py", ok=False)
        for path in (
            "generated/bad.py",
            "packages/web/src/generated/bad.ts",
            "docs/frozen/bad.md",
        ):
            self.skips(path)

    def missing(self):
        before = self.state()
        for name in ("fmt", "fmt-check", "lint"):
            result = self.hook(name, "--file", "missing.py", ok=False)
            self.require(
                "No such file or directory" in result.stdout + result.stderr,
                "Matching missing path reaches native tool and fails",
            )
        self.preserved(
            before, self.state(), "Missing-path failures preserve all inputs"
        )
        self.run(
            ["uv", "run", "--locked", "--no-sync", "ruff", "format", "missing.py"],
            ok=False,
        )
        self.skips("missing.txt")

    def skips(self, path):
        before = self.state()
        for name in ("fmt", "fmt-check", "lint"):
            result = self.hook(name, "--file", path)
            self.require("skip" in result.stdout.lower(), "Expected skip is visible")
        self.preserved(before, self.state(), "Skipped invocations preserve all inputs")

    def context(self):
        write(self.repo, WEB, DIRTY_TS)
        self.hook("fmt", "--file", WEB, cwd=self.repo / "packages/web")
        self.require(
            (self.repo / WEB).read_text()
            == "export const value = { message: 'hello' };\n",
            "Invocation below Git root retains repository-relative selection and local policy",
        )
        result = self.hook("lint", "--file", "Cargo.toml")
        self.require(
            "rust (skip)" not in result.stdout and "rust (" in result.stdout,
            "Manifest triggers project-scoped job without {files}",
        )
        result = self.hook("lint", "--file", "README.md")
        self.require(
            "rust (skip)" in result.stdout,
            "Nonmatching path does not run project-scoped job",
        )

    def failure(self, gate):
        path, content, diagnostic, direct = {
            "lint": (
                "root.py",
                "import os\n",
                "F401",
                ["uv", "run", "--locked", "--no-sync", "ruff", "check", "root.py"],
            ),
            "fmt-check": (
                "root.py",
                DIRTY_PY,
                "reformat",
                [
                    "uv",
                    "run",
                    "--locked",
                    "--no-sync",
                    "ruff",
                    "format",
                    "--check",
                    "root.py",
                ],
            ),
            "typecheck": (
                WEB,
                "export const value: number = 'hello';\n",
                "TS2322",
                ["pnpm", "exec", "tsc", "--project", "packages/web", "--noEmit"],
            ),
            "tests": (
                "model.mjs",
                "export const value = 2;\n",
                "ERR_ASSERTION",
                ["node", "--test", "behavior.test.mjs"],
            ),
        }[gate]
        write(self.repo, path, content)
        result = self.run(direct, ok=False)
        self.require(
            diagnostic in result.stdout + result.stderr,
            "Native command diagnoses injected defect",
        )
        result = self.hook("check", "--file", "README.md", ok=False)
        self.require(
            diagnostic in result.stdout + result.stderr,
            "Aggregate propagates the same failure outside outer --file selection",
        )

    def workspace(self):
        for crate in ("a", "b"):
            write(self.repo, f"crates/{crate}/src/lib.rs", "pub fn value()->u8{1}\n")
        self.hook("fmt-check", "--file", "crates/a/src/lib.rs", ok=False)
        self.hook("fmt", "--file", "crates/a/src/lib.rs")
        self.require(
            (self.repo / "crates/b/src/lib.rs").read_text()
            == "pub fn value() -> u8 {\n    1\n}\n",
            "Cargo formatter intentionally covers unselected workspace crate",
        )
        self.hook("fmt-check", "--file", "crates/a/src/lib.rs")

    def staging(self, fail):
        self.run(["pnpm", "exec", "lefthook", "install", "pre-commit"], ok=True)
        write(self.repo, WEB, "export const staged={value:1};\n")
        self.git("add", "--", WEB)
        write(
            self.repo,
            WEB,
            "export const staged={value:1};\nexport const unstaged={value:2};\n",
        )
        write(self.repo, "packages/web/src/nested/deep.ts", DIRTY_TS)
        if fail:
            write(self.repo, "packages/web/src/broken.ts", "export const broken = ;\n")
            self.git("add", "--", "packages/web/src/broken.ts")
        before = self.git("rev-parse", "HEAD").stdout
        result = self.git(
            "commit", "-m", "test: exercise installed pre-commit", ok=not fail
        )
        self.require(
            "web" in result.stdout + result.stderr,
            "Installed pre-commit actually executes formatter",
        )
        staged = self.git("show", ":" + WEB).stdout
        self.require("unstaged" not in staged, "Unstaged content stays outside index")
        self.require(
            "export const unstaged={value:2};" in (self.repo / WEB).read_text(),
            "Unstaged content survives hook exactly",
        )
        self.require(
            (self.repo / "packages/web/src/nested/deep.ts").read_text() == DIRTY_TS,
            "Unstaged-only file is not formatted",
        )
        after = self.git("rev-parse", "HEAD").stdout
        self.require(
            (before == after) == fail, "Commit succeeds or is blocked as expected"
        )
        if not fail:
            self.require(
                staged == "export const staged = { value: 1 };\n",
                "Formatted staged content enters commit",
            )
        else:
            self.require(
                "SyntaxError" in result.stdout + result.stderr,
                "Failed commit preserves parser diagnostic",
            )

    def output(self, mode):
        env = {}
        if mode == "quiet":
            env["LEFTHOOK_OUTPUT"] = "false"
        elif mode == "verbose":
            env["LEFTHOOK_OUTPUT"] = "summary,success,failure,skips,execution_out"
        result = self.hook("output-probe", env=env)
        text = result.stdout + result.stderr
        self.require(
            ("PROBE_STDOUT" in text) == (mode == "verbose"),
            "Successful stdout follows verbosity policy",
        )
        self.require(
            ("PROBE_WARNING" in text) == (mode == "verbose"),
            "Successful stderr follows verbosity policy",
        )
        self.require(
            not text.strip() if mode == "quiet" else "output-probe" in text,
            "Quiet mode or success summary behaves as documented",
        )
        result = self.hook("output-probe", env={**env, "PROBE_EXIT": "7"}, ok=False)
        self.require(
            "PROBE_WARNING" in result.stdout + result.stderr,
            "Failure diagnostics survive verbosity override",
        )

    def mutation(self, kind):
        config = self.config
        if kind == "wrong-glob":
            self.configure(config.replace('["*.py", "**/*.py"]', '["no-match/*.py"]'))
            write(self.repo, "root.py", DIRTY_PY)
            self.run(
                [
                    "uv",
                    "run",
                    "--locked",
                    "--no-sync",
                    "ruff",
                    "format",
                    "--check",
                    "root.py",
                ],
                ok=False,
            )
            result = self.hook("fmt-check", "--file", "root.py")
            self.require(
                "python (skip)" in result.stdout,
                "Selection oracle detects false success caused by bad glob",
            )
        elif kind == "scope-mismatch":
            self.configure(
                config.replace(
                    "    - <<: *python\n      run: uv run --locked --no-sync ruff format --check",
                    '    - <<: *python\n      exclude: ["root.py", "generated/**", "ignored/**"]\n      run: uv run --locked --no-sync ruff format --check',
                )
            )
            write(self.repo, "root.py", DIRTY_PY)
            self.hook("fmt-check", "--file", "root.py")
            self.hook("fmt", "--file", "root.py")
            self.require(
                (self.repo / "root.py").read_text() != DIRTY_PY,
                "Write/check parity oracle detects skipped dirty input",
            )
        elif kind == "suppressed-failure":
            self.configure(
                config.replace(
                    "run: pnpm exec lefthook run lint --all-files",
                    "run: pnpm exec lefthook run lint --all-files || true",
                )
            )
            write(self.repo, "root.py", "import os\n")
            self.hook("lint", "--all-files", ok=False)
            result = self.hook("check", "--job", "lint")
            self.require(
                result.returncode == 0,
                "Leaf/aggregate exit comparison detects suppressed failure",
            )
        else:
            self.configure(
                config.replace("ruff format --check {files}", "ruff format {files}")
            )
            write(self.repo, "root.py", DIRTY_PY)
            before = self.state()
            self.hook("fmt-check", "--file", "root.py", readonly=False)
            after = self.state()
            self.require(
                before != after,
                "Source hash oracle detects a mutating check",
                {"before": digest(before), "after": digest(after)},
            )

    def regression(self):
        repo = self.root / "engineering-standard-regression"
        self.git(
            "clone",
            "--quiet",
            "--no-hardlinks",
            str(self.source),
            str(repo),
            cwd=self.root,
        )
        self.git("checkout", "--detach", self.manifest["source_head"], cwd=repo)
        self.install(repo)
        before = self.state(repo)
        self.run(["pnpm", "exec", "lefthook", "validate"], cwd=repo, ok=True)
        try:
            command = (
                ["mise", "run", "check"]
                if (repo / "mise.lock").exists()
                else ["pnpm", "--silent", "check"]
            )
            self.run(
                command,
                cwd=repo,
                env={"MISE_TRUSTED_CONFIG_PATHS": str(repo)},
                ok=True,
                timeout=600,
            )
        finally:
            self.preserved(
                before,
                self.state(repo),
                "Full committed-repository gate preserves source and index",
            )

    def save(self):
        summary = {
            "passed": all(case["passed"] for case in self.cases),
            "cases": len(self.cases),
            "failed_cases": [case["name"] for case in self.cases if not case["passed"]],
            "commands": len(self.commands),
            "hook_invocations": sum(
                command["argv"][:4] == ["pnpm", "exec", "lefthook", "run"]
                for command in self.commands
            ),
            "assertions": sum(len(case["assertions"]) for case in self.cases),
            "results": self.cases,
        }
        for name, data in (
            ("results.json", summary),
            ("commands.json", self.commands),
        ):
            write(
                self.root,
                name,
                self.portable(json.dumps(data, indent=2, ensure_ascii=False)) + "\n",
            )
        self.manifest["artifacts"] = {
            name: digest((self.root / name).read_bytes())
            for name in ("results.json", "commands.json")
        }
        write(
            self.root,
            "manifest.json",
            self.portable(json.dumps(self.manifest, indent=2)) + "\n",
        )

    def evaluate(self):
        print(f"Evaluation workspace: {self.root}", flush=True)
        try:
            self.freeze()
            self.setup()
            self.case("validate-and-clean-baseline", self.validate)
            for matcher in ("gobwas", "doublestar"):
                self.case(
                    f"selection-and-native-parity-{matcher}",
                    lambda m=matcher: self.selections(m),
                )
            for name, args in (("bare-default", ()), ("all-files", ("--all-files",))):
                self.case(name, lambda a=args: self.defaults(a))
            self.case("repeated-untracked-and-unusual-paths", self.explicit)
            self.case("matcher-depth-and-doublestar-exclusions", self.matcher_depth)
            for path in (
                "generated/bad.py",
                "ignored/bad.py",
                "packages/web/src/generated/bad.ts",
                "docs/frozen/bad.md",
                "package.json",
            ):
                self.case(f"skip-{path}", lambda p=path: self.skips(p))
            self.case("missing-matching-and-nonmatching-paths", self.missing)
            self.case("package-context-and-manifest-trigger", self.context)
            for gate in ("lint", "fmt-check", "typecheck", "tests"):
                self.case(f"aggregate-failure-{gate}", lambda g=gate: self.failure(g))
            self.case("workspace-wide-formatting", self.workspace)
            for fail in (False, True):
                self.case(
                    f"installed-partial-staging-{'failure' if fail else 'success'}",
                    lambda f=fail: self.staging(f),
                )
            for mode in ("default", "quiet", "verbose"):
                self.case(f"output-{mode}", lambda m=mode: self.output(m))
            for kind in (
                "wrong-glob",
                "scope-mismatch",
                "suppressed-failure",
                "mutating-check",
            ):
                self.case(f"mutation-{kind}", lambda k=kind: self.mutation(k))
            self.case("committed-repository-regression", self.regression, reset=False)
        except Exception:
            self.cases.append(
                {
                    **self.active,
                    "passed": False,
                    "error": self.portable(traceback.format_exc()),
                }
            )
        finally:
            if hasattr(self, "before_source"):
                self.case(
                    "original-source-preservation",
                    lambda: self.preserved(
                        self.before_source,
                        self.state(self.source),
                        "Original repository content, HEAD, status, and index preserved",
                    ),
                    reset=False,
                )
            self.save()
        return all(case["passed"] for case in self.cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        help="Export portable evidence after checking original-source preservation",
    )
    parser.add_argument(
        "--calibration-run",
        type=Path,
        help="Include an earlier run's original evidence in the export",
    )
    args = parser.parse_args()
    if not args.scratch.is_dir():
        parser.error("--scratch must be an existing temporary directory")
    evaluation = Evaluation(args.source.resolve(), args.scratch.resolve())
    passed = evaluation.evaluate()
    if args.output:
        args.output.mkdir(parents=True, exist_ok=False)
        for name in ("manifest.json", "results.json", "commands.json"):
            shutil.copy2(evaluation.root / name, args.output / name)
        shutil.copytree(evaluation.root / "inputs", args.output / "inputs")
        if args.calibration_run:
            calibration = args.output / "calibration"
            calibration.mkdir()
            for name in ("manifest.json", "results.json", "commands.json"):
                shutil.copy2(args.calibration_run / name, calibration / name)
            shutil.copytree(args.calibration_run / "inputs", calibration / "inputs")
            manifest = json.loads((args.output / "manifest.json").read_text())
            manifest["calibration_artifacts"] = {
                name: digest((calibration / name).read_bytes())
                for name in ("manifest.json", "results.json", "commands.json")
            }
            write(args.output, "manifest.json", json.dumps(manifest, indent=2) + "\n")
    print(
        f"{'PASS' if passed else 'FAIL'}: {len(evaluation.cases)} cases; evidence: {evaluation.root}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
