"""Deterministic comparisons against real project-selected formatting engines."""

from __future__ import annotations

import json
import math
import os
import statistics
import time
from collections import Counter
from pathlib import Path

from harness import Harness, digest, save

PRETTIER = "packages/web-solid/node_modules/prettier/bin/prettier.cjs"
MARKDOWNLINT = "node_modules/markdownlint-cli2/markdownlint-cli2-bin.mjs"


def config(h, *, incremental=False, cache_keys=False, markdownlint=False):
    commands = [
        {"command": "rustfmt --edition 2024", "exts": ["rs"]},
        {
            "command": f'node {PRETTIER} --stdin-filepath "{{{{{{file_path}}}}}}" --ignore-path packages/web-solid/.prettierignore',
            "exts": ["ts", "tsx", "css"],
        },
        {
            "command": f'node {PRETTIER} --stdin-filepath "{{{{{{file_path}}}}}}"',
            "exts": ["md", "mdx"],
        },
        {"command": 'ruff format --stdin-filename "{{{file_path}}}" -', "exts": ["py"]},
        {"command": "terraform fmt -", "exts": ["tf"]},
    ]
    if markdownlint:
        commands[2] = {
            "command": f'node {MARKDOWNLINT} --format "{{{{{{file_path}}}}}}"',
            "exts": ["md"],
        }
    if cache_keys:
        keys = [
            ["rust-toolchain.toml"],
            ["pnpm-lock.yaml", "packages/web-solid/.prettierignore"],
            ["pnpm-lock.yaml"],
            ["uv.lock", "pyproject.toml"],
            ["terraform/.terraform.lock.hcl"],
        ]
        for command, files in zip(commands, keys):
            command["cacheKeyFiles"] = files
    return {
        "incremental": incremental,
        "includes": [
            "**/*.md",
            "crates/**/*.rs",
            "packages/web-solid/src/**/*.{ts,tsx,css}",
            "python/**/*.py",
            "terraform/**/*.tf",
            ".format-eval/**/*",
        ],
        "excludes": [
            "**/node_modules/**",
            "**/target/**",
            "**/.git/**",
            ".agents/**",
            ".claude/**",
            "notes/**",
            "CLAUDE.md",
            "packages/web-solid/src/openapi/schema.ts",
            "**/*.spec.ts",
            "**/*.spec.tsx",
            ".format-eval/ignored/**",
        ],
        "exec": {"cwd": "${configDir}", "commands": commands},
        "plugins": [h.manifest["plugin"]],
    }


def direct(h, path, data, *, repo=None, markdownlint=False):
    repo = repo or h.candidate
    path = Path(path)
    if path.suffix == ".rs":
        command = ["rustfmt", "--edition", "2024"]
    elif path.suffix == ".py":
        command = ["ruff", "format", "--stdin-filename", repo / path, "-"]
    elif path.suffix == ".tf":
        command = ["terraform", "fmt", "-"]
    elif markdownlint:
        command = ["node", MARKDOWNLINT, "--format", repo / path]
    else:
        command = [
            "node",
            PRETTIER,
            "--stdin-filepath",
            repo / path,
        ]
        if path.suffix in (".ts", ".tsx", ".css"):
            command += ["--ignore-path", "packages/web-solid/.prettierignore"]
    return h.run(command, cwd=repo, data=data, label="direct")


def put(repo, path, data):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data if isinstance(data, bytes) else data.encode())
    return target


def samples():
    return {
        "basic.rs": 'fn main(){let x=vec![1,2,3];println!("{:?}",x);}\n',
        "async.rs": "pub async fn answer()->u32{42}\n",
        "macros.rs": "macro_rules! number {()=>{42};}\nfn main(){let _=number!();}\n",
        "module.rs": "mod missing_child;\npub fn parent( )->u8{1}\n",
        "basic.ts": 'export const x={message:"hello",values:[1,2,3]}\n',
        "basic.tsx": 'export const View=()=> <div class="item"><span>Hello</span></div>\n',
        "basic.css": ".item{color:red;background:light-dark(white,black)}\n",
        "basic.md": "# Title\n\n-   first\n-   second\n\n|A|B|\n|-|-|\n|1|2|\n",
        "features.md": "---\ntitle: Example\n---\n\n# Example\n\n1. first\n2. second\n\n> a quote\n\n```ts\nconst x={a:1,b:2}\n```\n\n[link](https://example.com)\n\n"
        + "A long sentence with words. " * 15
        + "\n",
        "toc.md": "# Title\n\n<!-- toc -->\n\n<!-- tocstop -->\n\n## Second heading\n\nText.\n",
        "basic.py": "def f(x:int)->int:\n return x+1\n",
        "basic.tf": "locals {\n a=1\n longer_name =2\n}\n",
        "space 日本語.ts": "export const name={a:1,b:2}\n",
        "amp&quote'\".ts": "export const name={a:1,b:2}\n",
        "crlf.ts": b"export const x={a:1}\r\n",
        "bom.ts": b"\xef\xbb\xbfexport const x={a:1}\n",
        "no-newline.md": "# Heading\n\nText",
        "empty.md": "",
    }


def fixture_path(section, name):
    base = (
        "packages/web-solid/src/format-eval"
        if Path(name).suffix in (".ts", ".tsx", ".css")
        else ".format-eval"
    )
    return Path(base) / section / name


def pilot(h):
    save(h.candidate / "dprint.json", config(h))
    result = {"configuration": config(h), "cases": []}
    h.require(["dprint", "output-resolved-config"], label="resolved-config")
    for name, content in samples().items():
        path = fixture_path("pilot", name)
        file = put(h.candidate, path, content)
        data = file.read_bytes()
        baseline, expected, _ = direct(h, path, data)
        candidate, actual, stderr = h.dprint("fmt", "--stdin", file, data=data)
        result["cases"].append(
            {
                "path": str(path),
                "direct": baseline,
                "candidate": candidate,
                "equal": expected == actual,
                "changed": data != actual,
                "input_preserved": file.read_bytes() == data,
                "diagnostic": stderr.decode(errors="replace")[:1000],
            }
        )
    # The documented double-brace template HTML-escapes path characters.
    probe = put(
        h.candidate,
        ".format-eval/path-probe.cjs",
        'process.stdout.write(process.argv[2]+"\\n");\n',
    )
    probe_file = put(h.candidate, ".format-eval/pilot/space & 日本語.ctx", "input\n")
    result["path_templates"] = {}
    for template in ("{{file_path}}", "{{{file_path}}}"):
        probe_config = config(h)
        probe_config["exec"]["commands"] = [
            {"command": f'node {probe} "{template}"', "exts": ["ctx"]}
        ]
        save(h.candidate / "probe.json", probe_config)
        command, output, _ = h.dprint(
            "fmt", "--config", "probe.json", "--stdin", probe_file, data=b"input\n"
        )
        result["path_templates"][template] = {
            "command": command,
            "exact_path": output.decode().rstrip() == str(probe_file),
            "output": output.decode(),
        }
    result["markdownlint"] = []
    md_config = config(h, markdownlint=True)
    save(h.candidate / "markdownlint.dprint.json", md_config)
    for name in ("basic.md", "features.md", "no-newline.md"):
        path = Path(".format-eval/pilot") / name
        data = (h.candidate / path).read_bytes()
        baseline, expected, _ = direct(h, path, data, markdownlint=True)
        candidate, actual, stderr = h.dprint(
            "fmt",
            "--config",
            "markdownlint.dprint.json",
            "--stdin",
            h.candidate / path,
            data=data,
        )
        result["markdownlint"].append(
            {
                "path": str(path),
                "direct": baseline,
                "candidate": candidate,
                "equal": expected == actual,
                "diagnostic": stderr.decode()[:1000],
            }
        )
    h.record_phase("pilot", result)


def corpus(h):
    cfg = config(h)
    save(h.candidate / "dprint.json", cfg)
    # Freeze all generated cases before comparing, including nested project settings.
    for repo in (h.baseline, h.candidate):
        for name, content in samples().items():
            put(repo, fixture_path("corpus", name), content)
        put(
            repo,
            "packages/web-solid/src/format-eval/corpus/nested/.prettierrc.json",
            '{"singleQuote":true,"tabWidth":4}\n',
        )
        put(
            repo,
            "packages/web-solid/src/format-eval/corpus/nested/input.ts",
            'export const nested={text:"hello",values:[1,2,3]}\n',
        )
        put(
            repo,
            ".format-eval/corpus/nested/pyproject.toml",
            '[tool.ruff.format]\nquote-style = "single"\n',
        )
        put(repo, ".format-eval/corpus/nested/input.py", 'x={"greeting":"hello"}\n')
    paths = h.require(["dprint", "output-file-paths"]).decode().splitlines()
    # Pilot fixtures are development data, not part of the frozen main corpus.
    paths = sorted(
        str(Path(p).relative_to(h.candidate))
        for p in paths
        if "/format-eval/pilot/" not in p and "/.format-eval/pilot/" not in p
    )
    inputs = {p: (h.candidate / p).read_bytes() for p in paths}
    freeze = {
        "config": cfg,
        "config_sha256": digest((h.candidate / "dprint.json").read_bytes()),
        "input_sha256": {p: digest(b) for p, b in inputs.items()},
    }
    save(h.artifacts / "freeze.json", freeze)
    before = h.snapshot(paths=paths)
    check_before, _, _ = h.dprint("check", "--list-different", *paths, timeout=180)
    preserved = before == h.snapshot(paths=paths)
    rows = []
    for path, data in inputs.items():
        baseline, expected, _ = direct(h, path, data, repo=h.baseline)
        candidate, actual, _ = h.dprint("fmt", "--stdin", h.candidate / path, data=data)
        second, stable, _ = (
            h.dprint("fmt", "--stdin", h.candidate / path, data=actual)
            if candidate["code"] == 0
            else ({"code": None}, b"", b"")
        )
        row = {
            "path": path,
            "bytes": len(data),
            "input_sha256": digest(data),
            "direct": baseline,
            "candidate": candidate,
            "second_code": second["code"],
            "equal": expected == actual,
            "idempotent": actual == stable,
            "direct_sha256": digest(expected),
            "candidate_sha256": digest(actual),
            "changed": data != actual,
        }
        rows.append(row)
        if baseline["code"] == 0:
            put(h.baseline, path, expected)
    bulk, _, _ = h.dprint("fmt", *paths, timeout=180)
    after = h.snapshot(paths=paths)
    expected_hashes = {
        r["path"]: r["candidate_sha256"] for r in rows if r["candidate"]["code"] == 0
    }
    final_check, _, _ = h.dprint("check", "--list-different", *paths, timeout=180)
    bulk_second, _, _ = h.dprint("fmt", *paths, timeout=180)
    result = {
        "counts": dict(Counter(Path(p).suffix for p in paths)),
        "files": len(paths),
        "changed": sum(r["changed"] for r in rows),
        "mismatches": [r["path"] for r in rows if not r["equal"]],
        "errors": [
            r["path"] for r in rows if r["direct"]["code"] or r["candidate"]["code"]
        ],
        "non_idempotent": [r["path"] for r in rows if not r["idempotent"]],
        "check_before": check_before,
        "check_preserved": preserved,
        "bulk": bulk,
        "bulk_matches_stdin": after == expected_hashes,
        "final_check": final_check,
        "bulk_second": bulk_second,
        "bulk_idempotent": after == h.snapshot(paths=paths),
        "rows": rows,
    }
    h.record_phase("corpus", result)


def run_phase(h: Harness, args):
    if args.phase == "export":
        from export import export

        if args.output is None:
            raise ValueError("export requires --output")
        export(h, args.output)
        return
    if args.phase == "extensions":
        from extensions import extensions

        extensions(h)
        return
    if args.phase in (
        "compatibility",
        "rust-compatibility",
        "hooks",
        "editors",
        "vscode",
        "representative",
        "example",
        "editor-actions",
    ):
        import integrations

        getattr(integrations, args.phase.replace("-", "_"))(h)
        return
    functions = {
        "pilot": pilot,
        "corpus": corpus,
        "behavior": behavior,
        "timing": timing,
    }
    if args.phase not in functions:
        raise ValueError(f"Phase not implemented: {args.phase}")
    functions[args.phase](h)


def behavior(h):
    save(h.candidate / "dprint.json", config(h))
    rows = []

    def check(name, predicate, **evidence):
        rows.append({"name": name, "pass": bool(predicate), **evidence})

    for name, text in {
        "invalid.ts": "const = {",
        "invalid.rs": "fn main( {",
        "invalid.py": "def f(:",
        "invalid.tf": "locals { a = [",
    }.items():
        path = fixture_path("behavior", name)
        file = put(h.candidate, path, text)
        before = file.read_bytes()
        for verb in ("fmt", "check"):
            cmd, stdout, stderr = h.dprint(verb, file)
            check(
                f"{name}-{verb}",
                cmd["code"] != 0 and file.read_bytes() == before and bool(stderr),
                command=cmd,
                diagnostic=stderr.decode()[:1000],
            )
        file.unlink()

    source = put(h.candidate, ".format-eval/behavior/failure.probe", "original\n")
    scripts = {
        "nonzero": 'process.stderr.write("intentional failure");process.exit(7);',
        "signal": 'process.kill(process.pid,"SIGTERM");',
        "empty-small": "process.exit(0);",
    }
    for name, script in scripts.items():
        helper = put(h.candidate, f".format-eval/behavior/{name}.cjs", script)
        cfg = config(h)
        cfg["exec"]["commands"] = [{"command": f"node {helper}", "exts": ["probe"]}]
        save(h.candidate / "behavior.json", cfg)
        cmd, out, err = h.dprint(
            "fmt",
            "--config",
            "behavior.json",
            "--stdin",
            source,
            data=b"original\n",
            timeout=5,
        )
        if name == "empty-small":
            check(
                "empty-output-small-is-not-protected",
                cmd["code"] == 0 and out == b"",
                command=cmd,
            )
            long_cmd, long_out, _ = h.dprint(
                "fmt", "--config", "behavior.json", "--stdin", source, data=b"x" * 101
            )
            check(
                "empty-output-large-is-rejected",
                long_cmd["code"] != 0 and not long_out,
                command=long_cmd,
            )
        else:
            check(
                name + "-visible",
                cmd["code"] != 0 and bool(err) and not cmd["timeout"],
                command=cmd,
                diagnostic=err.decode()[:1000],
            )
    cfg = config(h)
    cfg["exec"]["commands"] = [
        {"command": "nonexistent-formatter-eval-46075", "exts": ["probe"]}
    ]
    save(h.candidate / "behavior.json", cfg)
    cmd, _, err = h.dprint("fmt", "--config", "behavior.json", source)
    check(
        "missing-tool-preserves-input",
        cmd["code"] != 0 and source.read_text() == "original\n",
        command=cmd,
        diagnostic=err.decode()[:1000],
    )
    put(h.candidate, "invalid-config.json", '{"exec":')
    cmd, _, _ = h.dprint("check", "--config", "invalid-config.json", source)
    check(
        "invalid-config-fails",
        cmd["code"] != 0 and source.read_text() == "original\n",
        command=cmd,
    )

    # A finite child lets the probe observe cleanup without leaving an orphan.
    pidfile = h.artifacts / "timeout-child.pid"
    finished = h.artifacts / "timeout-child-finished"
    for marker in (pidfile, finished):
        marker.unlink(missing_ok=True)
    helper = put(
        h.candidate,
        ".format-eval/behavior/sleep.cjs",
        f'const fs=require("fs");fs.writeFileSync({json.dumps(str(pidfile))},String(process.pid));setTimeout(()=>{{fs.writeFileSync({json.dumps(str(finished))},"finished");process.stdout.write("original\\n")}},2500);',
    )
    cfg["exec"]["commands"][0]["command"] = f"node {helper}"
    cfg["exec"]["timeout"] = 1
    save(h.candidate / "behavior.json", cfg)
    cmd, _, err = h.dprint("fmt", "--config", "behavior.json", source, timeout=8)
    alive_at_return = False
    if pidfile.exists():
        try:
            os.kill(int(pidfile.read_text()), 0)
            alive_at_return = True
        except ProcessLookupError:
            pass
    time.sleep(2.7)
    check(
        "timeout-visible-input-preserved",
        cmd["code"] != 0 and source.read_text() == "original\n",
        command=cmd,
        diagnostic=err.decode()[:1000],
        child_alive_at_return=alive_at_return,
        child_completed_after_timeout=finished.exists(),
    )

    ignored = put(h.candidate, ".format-eval/ignored/excluded.md", "#Title\n")
    unsupported = put(h.candidate, ".format-eval/behavior/unknown.zzz", "unchanged\n")
    for file in (ignored, unsupported):
        before = file.read_bytes()
        cmd, _, _ = h.dprint("check", file)
        stdin_cmd, out, _ = h.dprint("fmt", "--stdin", file, data=before)
        check(
            f"selection-{file.name}",
            cmd["code"] == 14 and before == file.read_bytes(),
            command=cmd,
            stdin_command=stdin_cmd,
            stdin_passthrough=out == before,
        )
    web_file = put(
        h.candidate, fixture_path("behavior", "discovered.ts"), "const x={a:1}\n"
    )
    data = web_file.read_bytes()
    _, expected, _ = direct(h, web_file.relative_to(h.candidate), data)
    cmd, out, _ = h.dprint("fmt", "--stdin", web_file, data=data, cwd=web_file.parent)
    check(
        "ancestor-discovery-cwd",
        cmd["code"] == 0 and out == expected and out != data,
        command=cmd,
    )
    before_all = h.snapshot()
    cmd, _, _ = h.dprint("check", "--list-different", web_file)
    check(
        "check-20-no-write",
        cmd["code"] == 20
        and data == web_file.read_bytes()
        and before_all == h.snapshot(),
        command=cmd,
    )

    # Native rustfmt file-context discovery differs from stdin. A scoped dprint
    # config is the declarative remedy for this uniformly configured subtree.
    nested = h.candidate / ".format-eval/behavior/nested-rust"
    rust = put(
        nested,
        "input.rs",
        'fn main(){let words=vec!["one","two","three"];println!("{:?}",words);}\n',
    )
    put(nested, "rustfmt.toml", "max_width = 40\n")
    data = rust.read_bytes()
    h.require(["rustfmt", "--edition", "2021", rust], cwd=nested)
    expected = rust.read_bytes()
    rust.write_bytes(data)
    cmd, out, _ = h.dprint("fmt", "--stdin", rust, data=data)
    check(
        "root-rust-config-loses-nested-context",
        cmd["code"] == 0 and out != expected,
        command=cmd,
    )
    nested_cfg = {
        "incremental": False,
        "exec": {
            "cwd": "${configDir}",
            "commands": [{"command": "rustfmt --edition 2021", "exts": ["rs"]}],
        },
        "plugins": [h.manifest["plugin"]],
    }
    save(nested / "dprint.json", nested_cfg)
    cmd, out, _ = h.dprint("fmt", "--stdin", rust, data=data)
    check(
        "nested-dprint-restores-rust-context",
        cmd["code"] == 0 and out == expected,
        command=cmd,
    )

    cache_results = []
    for variant in ("no-keys", "keys", "disabled"):
        path = fixture_path("cache", f"{variant}/input.ts")
        file = put(h.candidate, path, 'const message="hello";\n')
        prettier_cfg = file.parent / ".prettierrc.json"
        save(prettier_cfg, {"singleQuote": False})
        cache_cfg = config(
            h, incremental=variant != "disabled", cache_keys=variant == "keys"
        )
        if variant == "keys":
            cache_cfg["exec"]["commands"][1]["cacheKeyFiles"].append(
                str(prettier_cfg.relative_to(h.candidate))
            )
        config_file = h.candidate / f"cache-{variant}.json"
        save(config_file, cache_cfg)
        warm, _, _ = h.dprint("fmt", "--config", config_file, file)
        save(prettier_cfg, {"singleQuote": True})
        cached, _, _ = h.dprint("check", "--config", config_file, file)
        uncached, _, _ = h.dprint(
            "check", "--config", config_file, "--incremental=false", file
        )
        cache_results.append(
            {
                "variant": variant,
                "warm": warm,
                "cached": cached,
                "uncached": uncached,
                "agrees": cached["code"] == uncached["code"],
            }
        )
    # A change to executable contents is invisible unless tracked or cache-busted.
    helper = put(
        h.candidate,
        ".format-eval/behavior/version.cjs",
        'process.stdout.write("one\\n");',
    )
    cfg = config(h, incremental=True)
    cfg["exec"]["commands"] = [{"command": f"node {helper}", "exts": ["probe"]}]
    save(h.candidate / "version.json", cfg)
    version_file = put(h.candidate, ".format-eval/behavior/version.probe", "one\n")
    h.dprint("fmt", "--config", "version.json", version_file)
    helper.write_text('process.stdout.write("two\\n");')
    cached, _, _ = h.dprint("check", "--config", "version.json", version_file)
    uncached, _, _ = h.dprint(
        "check", "--config", "version.json", "--incremental=false", version_file
    )
    cfg["exec"]["cacheKey"] = "version-two"
    save(h.candidate / "version.json", cfg)
    busted, _, _ = h.dprint("check", "--config", "version.json", version_file)
    check(
        "version-change-requires-invalidation",
        cached["code"] == 0 and uncached["code"] == 20 and busted["code"] == 20,
        cached=cached,
        uncached=uncached,
        busted=busted,
    )
    save(h.candidate / "dprint.json", config(h))
    h.record_phase(
        "behavior",
        {
            "rows": rows,
            "cache": cache_results,
            "summary": {
                "probes": len(rows),
                "unexpected_results": [r["name"] for r in rows if not r["pass"]],
                "cache_agreement": {r["variant"]: r["agrees"] for r in cache_results},
                "timeout_child_alive": alive_at_return,
                "timeout_child_completed": finished.exists(),
            },
        },
    )


def distribution(values):
    ordered = sorted(values)
    return {
        "n": len(values),
        "p50_ms": statistics.median(values),
        "p95_ms": ordered[math.ceil(len(values) * 0.95) - 1],
        "max_ms": max(values),
    }


def timing(h):
    save(h.candidate / "dprint.json", config(h))
    result = {"warm": {}, "cache": {}, "startup": [], "rows": []}
    for name in ("basic.rs", "basic.tsx", "basic.md", "basic.py", "basic.tf"):
        path = fixture_path("timing", name)
        text = samples()[name]
        file = put(h.candidate, path, text)
        elapsed = {"direct": [], "dprint": []}
        for index in range(105):
            # New content every request; the first five pairs warm filesystem/tool caches.
            prefix = "#" if file.suffix in (".md", ".py") else "//"
            data = f"{prefix} sample {index}\n{text}".encode()
            pair = {}
            for arm in ("direct", "dprint") if index % 2 == 0 else ("dprint", "direct"):
                command, output, _ = (
                    direct(h, path, data)
                    if arm == "direct"
                    else h.dprint("fmt", "--stdin", file, data=data)
                )
                if command["code"] or command["timeout"]:
                    raise RuntimeError(command)
                pair[arm] = output
                if index >= 5:
                    elapsed[arm].append(command["ms"])
                    result["rows"].append(
                        {
                            "case": name,
                            "sample": index - 5,
                            "arm": arm,
                            "command": command,
                        }
                    )
            assert pair["direct"] == pair["dprint"]
            assert pair["dprint"] != data
        result["warm"][name] = {
            arm: distribution(values) for arm, values in elapsed.items()
        }
    file = h.candidate / fixture_path("timing", "basic.tsx")
    for variant in ("minimal", "incremental"):
        cfg = config(
            h, incremental=variant == "incremental", cache_keys=variant == "incremental"
        )
        save(h.candidate / "timing.json", cfg)
        h.require(["dprint", "fmt", "--config", "timing.json", file])
        values = []
        for index in range(100):
            cmd, _, _ = h.dprint("check", "--config", "timing.json", file)
            assert cmd["code"] == 0
            values.append(cmd["ms"])
        result["cache"][variant] = {**distribution(values), "samples_ms": values}
    # Cold dprint caches include plugin download/extraction; not an OS cold-cache claim.
    for index in range(3):
        env = {
            **h.env,
            "DPRINT_CACHE_DIR": str(
                h.root / f"environments/cold-cache-{time.time_ns()}-{index}"
            ),
        }
        cmd, _, _ = h.dprint(
            "fmt", "--stdin", file, data=samples()["basic.tsx"].encode(), env=env
        )
        result["startup"].append(cmd)
    paths = list(json.loads((h.artifacts / "freeze.json").read_text())["input_sha256"])
    for incremental in (False, True):
        save(
            h.candidate / "timing.json",
            config(h, incremental=incremental, cache_keys=incremental),
        )
        runs = []
        for _ in range(5):
            cmd, _, _ = h.dprint("fmt", "--config", "timing.json", *paths)
            runs.append(cmd)
        result[f"bulk_incremental_{incremental}"] = runs
    result["summary"] = {
        "warm": result["warm"],
        "unchanged_check": {
            k: {a: b for a, b in v.items() if a != "samples_ms"}
            for k, v in result["cache"].items()
        },
        "cold_start_ms": [r["ms"] for r in result["startup"]],
    }
    h.record_phase("timing", result)
