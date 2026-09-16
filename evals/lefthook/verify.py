#!/usr/bin/env python3
"""Exercise internal's native Lefthook hooks with real tools and disposable probes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def execute(cwd, args, *, input=None, env=None):
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        input=input,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=180,
        check=False,
    )


def git(repo, *args):
    result = execute(repo, ["git", *args])
    assert result.returncode == 0, result.stdout
    return result.stdout


def snapshot(repo):
    paths = git(repo, "ls-files", "-z").split("\0")
    return {
        path: hashlib.sha256((repo / path).read_bytes()).hexdigest()
        for path in paths
        if path and (repo / path).is_file()
    }


def configuration(repo, path):
    result = execute(
        repo,
        ["pnpm", "exec", "lefthook", "dump", "--format", "json"],
        env={**os.environ, "LEFTHOOK_CONFIG": str(path)},
    )
    assert result.returncode == 0, result.stdout
    resolved = json.loads(result.stdout)
    # Verbosity is a caller preference; commands and selection must still match.
    resolved.pop("output", None)
    return resolved


def verify(repo, scratch):
    example = (
        Path(__file__).resolve().parents[2]
        / "skills/engineering-standard/references/lefthook/lefthook.example.yml"
    )
    assert configuration(repo, repo / "lefthook.yml") == configuration(repo, example), (
        "Repository commands or selection differ from the published example"
    )
    rows = []
    created = []
    before = snapshot(repo)
    before_status = git(repo, "status", "--porcelain=v1", "-z")
    before_index = git(repo, "diff", "--cached", "--binary")
    env = {**os.environ, "NO_COLOR": "1"}

    def hook(cwd, name, *args, fail=False, quiet=False):
        command = ["pnpm", "exec", "lefthook", "run", name, "--no-auto-install", *args]
        call_env = {**env, "LEFTHOOK_OUTPUT": "false"} if quiet else env
        result = execute(cwd, command, env=call_env)
        assert (result.returncode != 0) == fail, (command, result.stdout)
        if quiet:
            assert not result.stdout.strip(), (command, result.stdout)
        rows.append({"hook": name, "args": list(args), "exit": result.returncode})
        return result

    def probe(path, content):
        target = repo / path
        assert target.parent.is_dir() and not target.exists(), target
        target.write_text(content)
        created.append(target)
        return target

    try:
        # Deliberately dirty untracked files prove --file overrides tracked defaults,
        # and exercise spaces, Unicode, apostrophes, and shell metacharacters.
        cases = [
            ("python/fetch/lefthook probe ü & ' case.py", "value=  1\n"),
            (
                "packages/web-solid/src/lefthook probe ü & ' case.ts",
                "export const value={a:1};\n",
            ),
            ("packages/web-solid/src/lefthook probe.css", ".probe{color:red}\n"),
            (
                "terraform/lefthook probe ü & ' case.tf",
                "locals {\nprobe={a=1,b=2}\n}\n",
            ),
            ("lefthook probe ü & ' case.md", "# Lefthook probe\n\n-   item\n"),
            ("packages/web-solid/lefthook probe.md", "# Lefthook probe\n\n-   item\n"),
        ]
        for path, content in cases:
            target = probe(path, content)
            if path.endswith(".ts"):
                hook(repo, "fmt-check", "--job", "prettier", quiet=True)
            hook(repo, "fmt-check", "--file", path, fail=True)
            assert target.read_text() == content, path
            hook(repo, "fmt", "--file", path, quiet=True)
            formatted = target.read_text()
            assert formatted != content, path
            hook(repo, "fmt-check", "--file", path, quiet=True)
            hook(repo, "fmt", "--file", path, quiet=True)
            assert target.read_text() == formatted, path
            target.unlink()

        # A lint failure is independent of formatting and must leave the source alone.
        path = "python/fetch/lefthook-lint-probe.py"
        target = probe(path, "import os\n")
        result = hook(repo, "lint", "--file", path, fail=True)
        assert "F401" in result.stdout and target.read_text() == "import os\n"
        target.unlink()

        for path in (
            "packages/web-solid/src/lefthook-probe.spec.ts",
            ".agents/lefthook-probe.md",
        ):
            target = probe(path, "intentionally invalid input\n")
            hook(repo, "fmt", "--file", path, quiet=True)
            hook(repo, "fmt-check", "--file", path, quiet=True)
            assert target.read_text() == "intentionally invalid input\n"
            target.unlink()

        for name in ("fmt", "fmt-check", "lint"):
            hook(repo, name, "--file", "package.json", quiet=True)
        hook(repo, "lint", "--job", "rust", "--file", "package.json", quiet=True)
        hook(
            repo,
            "fmt-check",
            "--file",
            "packages/web-solid/src/openapi/schema.ts",
            quiet=True,
        )

        # The real agent hooks must normalize absolute paths and capture failed checks.
        path = "python/fetch/lefthook-agent-probe.py"
        target = probe(path, "value=  1\n")
        agent_env = {**env, "CLAUDE_PROJECT_DIR": str(repo)}
        stopped = execute(
            repo,
            ["bash", ".claude/hooks/lefthook-check.sh"],
            input='{"stop_hook_active": false}',
            env=agent_env,
        )
        decision = json.loads(stopped.stdout)
        assert stopped.returncode == 0 and decision["decision"] == "block", (
            stopped.stdout
        )
        assert "lefthook-agent-probe.py" in decision["reason"], stopped.stdout
        formatted = execute(
            repo,
            ["bash", ".claude/hooks/lefthook-fmt.sh"],
            input=json.dumps({"tool_input": {"file_path": str(target)}}),
            env=agent_env,
        )
        assert formatted.returncode == 0 and target.read_text() == "value = 1\n"
        hook(repo, "fmt-check", "--file", path, quiet=True)
        target.unlink()

        # Workspace-wide writes and index changes belong in an independent checkout.
        with tempfile.TemporaryDirectory(prefix="lefthook-", dir=scratch) as temp:
            clone = Path(temp) / "repo"
            git(scratch, "clone", "--quiet", "--shared", str(repo), str(clone))
            shutil.copy2(repo / "lefthook.yml", clone / "lefthook.yml")
            for relative in (
                "node_modules",
                "packages/web-solid/node_modules",
                ".venv",
            ):
                (clone / relative).symlink_to(repo / relative, target_is_directory=True)

            rust = "crates/http-api-core/src/lib.rs"
            with (clone / rust).open("a") as stream:
                stream.write("\npub fn lefthook_probe()->u8{1}\n")
            hook(clone, "fmt-check", "--file", rust, fail=True)
            hook(clone, "fmt", "--file", rust, quiet=True)
            hook(clone, "fmt-check", "--file", rust, quiet=True)
            hook(clone, "fmt", "--job", "python", quiet=True)
            hook(clone, "fmt-check", "--job", "python", quiet=True)

            partial = "packages/web-solid/src/lefthook-partial-probe.ts"
            (clone / partial).write_text("export const staged={value:1};\n")
            git(clone, "add", "--", partial)
            with (clone / partial).open("a") as stream:
                stream.write("export const unstaged={value:2};\n")
            hook(clone, "pre-commit", "--job", "prettier", quiet=True)
            staged = git(clone, "show", ":" + partial)
            assert staged == "export const staged = { value: 1 };\n", staged
            assert "unstaged" in (clone / partial).read_text()
            assert "unstaged" not in staged

    finally:
        for target in created:
            target.unlink(missing_ok=True)
        assert snapshot(repo) == before, (
            "Verification changed existing tracked file contents"
        )
        assert git(repo, "status", "--porcelain=v1", "-z") == before_status
        assert git(repo, "diff", "--cached", "--binary") == before_index

    print(
        json.dumps(
            {
                "repository": str(repo),
                "head": git(repo, "rev-parse", "HEAD").strip(),
                "configuration_sha256": hashlib.sha256(
                    (repo / "lefthook.yml").read_bytes()
                ).hexdigest(),
                "example_sha256": hashlib.sha256(example.read_bytes()).hexdigest(),
                "hook_invocations": len(rows),
                "source_and_index_preserved": True,
                "agent_hooks": "absolute-path formatting and blocking failure passed",
                "partial_staging": "passed in disposable checkout",
                "results": rows,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--scratch", required=True, type=Path)
    args = parser.parse_args()
    verify(args.repo.resolve(), args.scratch.resolve())
