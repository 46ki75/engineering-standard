"""Additional policy, path-selection, and process-lifecycle probes."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path

from experiments import MARKDOWNLINT, config, direct, put, samples
from harness import COMMIT, save
from integrations import clone


def extensions(h):
    repo = clone(h, "extension-probes")
    save(repo / "dprint.json", config(h))
    save(repo / "markdownlint.dprint.json", config(h, markdownlint=True))
    md_rows = []
    corpus = json.loads((h.artifacts / "corpus.json").read_text())["rows"]
    for row in corpus:
        path = row["path"]
        if not path.endswith(".md"):
            continue
        data = (
            samples()[Path(path).name].encode()
            if "format-eval" in path
            else h.require(["git", "show", f"{COMMIT}:{path}"], cwd=h.baseline)
        )
        file = put(repo, path, data)
        candidate, actual, _ = h.dprint(
            "fmt",
            "--config",
            "markdownlint.dprint.json",
            "--stdin",
            file,
            data=data,
            cwd=repo,
        )
        native, _, _ = h.run(["node", MARKDOWNLINT, "--fix", file], cwd=repo)
        expected = file.read_bytes()
        md_rows.append(
            {
                "path": path,
                "candidate": candidate,
                "native": native,
                "equal_to_native_fix": actual == expected,
                "prettier_differs": actual != direct(h, path, data, repo=repo)[1],
            }
        )
    selection = []
    probes = {
        ".claude/eval.md": False,
        ".agents/eval.md": False,
        "notes/eval.md": False,
        "packages/web-solid/src/format-eval/selection/ignored.spec.ts": False,
        "packages/web-solid/src/format-eval/selection/included.test.ts": True,
        "packages/web-solid/src/format-eval/selection/bracket[1].ts": True,
        "packages/web-solid/src/format-eval/selection/brace{a}.ts": True,
    }
    for path, covered in probes.items():
        data = (
            b"# Heading\n\n-   text\n"
            if path.endswith(".md")
            else b"export const value={a:1}\n"
        )
        file = put(repo, path, data)
        cmd, _, _ = h.dprint("fmt", "--", file, cwd=repo)
        verify, _, _ = h.dprint("check", "--", file, cwd=repo)
        selection.append(
            {
                "path": path,
                "covered": covered,
                "command": cmd,
                "check": verify,
                "changed": file.read_bytes() != data,
                "pass": (
                    cmd["code"] == 0
                    and verify["code"] == 0
                    and file.read_bytes() != data
                )
                if covered
                else (
                    cmd["code"] == 14
                    and verify["code"] == 14
                    and file.read_bytes() == data
                ),
            }
        )
    generated = repo / "packages/web-solid/src/openapi/schema.ts"
    original = generated.read_bytes()
    cmd, _, _ = h.dprint("fmt", generated, cwd=repo)
    selection.append(
        {
            "path": str(generated.relative_to(repo)),
            "covered": False,
            "command": cmd,
            "pass": cmd["code"] == 14 and generated.read_bytes() == original,
        }
    )
    # Exercise the project's normal uv resolution without installing application dependencies.
    sync, _, _ = h.run(
        ["uv", "sync", "--locked", "--only-dev", "--no-install-workspace"],
        cwd=repo,
        timeout=180,
    )
    ruff_file = put(repo, "python/format-eval.py", 'x={"a":1}\n')
    direct_ruff, expected, _ = direct(
        h, ruff_file.relative_to(repo), ruff_file.read_bytes(), repo=repo
    )
    uv_cfg = config(h)
    uv_cfg["exec"]["commands"][3]["command"] = (
        'uv run --locked --no-sync ruff format --stdin-filename "{{{file_path}}}" -'
    )
    save(repo / "uv.dprint.json", uv_cfg)
    delegated_ruff, actual, _ = h.dprint(
        "fmt",
        "--config",
        "uv.dprint.json",
        "--stdin",
        ruff_file,
        data=ruff_file.read_bytes(),
        cwd=repo,
    )

    source = put(repo, ".format-eval/unsafe.probe", "original\n")
    helper = put(
        repo,
        ".format-eval/write.cjs",
        'const fs=require("fs"),p=process.argv[2];const text=fs.readFileSync(p,"utf8").toUpperCase();fs.writeFileSync(p,text);process.stdout.write(text);',
    )
    cfg = config(h)
    cfg["exec"]["commands"] = [
        {
            "command": f'node {helper} "{{{{{{file_path}}}}}}"',
            "stdin": False,
            "exts": ["probe"],
        }
    ]
    save(repo / "file-writer.json", cfg)
    writer_check, _, _ = h.dprint(
        "check", "--config", "file-writer.json", source, cwd=repo
    )
    check_mutated = source.read_text() != "original\n"

    pidfile = h.artifacts / "cancel-child.pid"
    finished = h.artifacts / "cancel-child-finished"
    pidfile.unlink(missing_ok=True)
    finished.unlink(missing_ok=True)
    helper = put(
        repo,
        ".format-eval/cancel.cjs",
        f'const fs=require("fs");fs.writeFileSync({json.dumps(str(pidfile))},String(process.pid));setTimeout(()=>{{fs.writeFileSync({json.dumps(str(finished))},"finished");process.stdout.write("original\\n")}},2500);',
    )
    cfg["exec"]["commands"] = [{"command": f"node {helper}", "exts": ["probe"]}]
    save(repo / "cancel.json", cfg)
    command = [
        str(h.tools / "bin/dprint"),
        "fmt",
        "--config",
        "cancel.json",
        str(source),
    ]
    process = subprocess.Popen(
        command,
        cwd=repo,
        env=h.env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 5
        while (
            not pidfile.exists()
            and process.poll() is None
            and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        os.kill(process.pid, signal.SIGINT)
        stdout, stderr = process.communicate(timeout=5)
    except (subprocess.TimeoutExpired, ProcessLookupError):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
    time.sleep(2.7)
    cancellation = {
        "command": command,
        "exit": process.returncode,
        "signal": "SIGINT to CLI PID (not whole process group)",
        "child_started": pidfile.exists(),
        "child_completed": finished.exists(),
        "stdout": stdout.decode(),
        "stderr": stderr.decode(),
    }
    h.record_phase(
        "extensions",
        {
            "markdownlint": md_rows,
            "selection": selection,
            "uv": {
                "sync": sync,
                "direct": direct_ruff,
                "delegated": delegated_ruff,
                "equal": actual == expected,
            },
            "file_writer_check": writer_check,
            "file_writer_mutated_check_input": check_mutated,
            "cancellation": cancellation,
            "summary": {
                "markdownlint_cases": len(md_rows),
                "markdownlint_mismatches": [
                    r["path"] for r in md_rows if not r["equal_to_native_fix"]
                ],
                "markdown_engine_differences": sum(
                    r["prettier_differs"] for r in md_rows
                ),
                "selection_failures": [r["path"] for r in selection if not r["pass"]],
                "uv_equal": actual == expected,
                "unsafe_file_writer_mutates_check": check_mutated,
                "cancellation_child_completed": finished.exists(),
            },
        },
    )
