"""Actual hook/editor entry points and project compatibility checks."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from experiments import (
    MARKDOWNLINT,
    config,
    direct,
    fixture_path,
    put,
    samples,
)
from harness import COMMIT, HERE, digest, save


def clone(h, name):
    repo = h.root / name
    attempt = 1
    while repo.exists():
        attempt += 1
        repo = h.root / f"{name}-attempt-{attempt}"
    h.require(
        ["git", "clone", "--no-local", "--no-checkout", h.baseline, repo], cwd=h.root
    )
    h.require(["git", "checkout", "--detach", COMMIT], cwd=repo)
    for relative in ("node_modules", "packages/web-solid/node_modules"):
        (repo / relative).symlink_to(h.baseline / relative, target_is_directory=True)
    return repo


def compatibility(h):
    original = clone(h, "compatibility-original")
    formatted = clone(h, "compatibility-formatted")
    changed_paths = []
    for path in h.tracked(formatted):
        actual = h.candidate / path
        if (
            actual.is_file()
            and digest(actual.read_bytes()) != h.manifest["snapshot_hashes"][path]
        ):
            (formatted / path).write_bytes(actual.read_bytes())
            changed_paths.append(path)
    jobs = [
        ("rust-format", [], ["cargo", "fmt", "--all", "--", "--check"], 120),
        (
            "rust-clippy",
            [],
            ["cargo", "clippy", "--workspace", "--all-targets", "--", "-D", "warnings"],
            900,
        ),
        ("rust-tests", [], ["cargo", "test", "--workspace"], 900),
        ("web-format", ["packages", "web-solid"], ["pnpm", "fmt.check"], 120),
        ("web-eslint", ["packages", "web-solid"], ["pnpm", "lint"], 120),
        ("web-stylelint", ["packages", "web-solid"], ["pnpm", "lint.css"], 120),
        ("web-types", ["packages", "web-solid"], ["pnpm", "build.types"], 120),
        ("web-tests", ["packages", "web-solid"], ["pnpm", "test"], 180),
        ("python-format", [], ["ruff", "format", "--check", "python"], 120),
        ("python-lint", [], ["ruff", "check", "python"], 120),
        (
            "terraform-format",
            [],
            ["terraform", "fmt", "-check", "-recursive", "terraform"],
            120,
        ),
        ("markdown-lint", [], ["node", MARKDOWNLINT, "**/*.md"], 120),
    ]
    rows = []
    for name, cwd, command, timeout in jobs:
        row: dict = {"name": name}
        for arm, repo in (("original", original), ("formatted", formatted)):
            result, stdout, stderr = h.run(
                command, cwd=repo.joinpath(*cwd), timeout=timeout, label=f"{arm}-{name}"
            )
            row[arm] = result
            # Normalize clone locations for meaningful diagnostic comparisons.
            normalized = (
                (stdout + stderr).decode(errors="replace").replace(str(repo), "$REPO")
            )
            row[arm + "_diagnostic"] = normalized[-3000:]
        row["same_exit"] = row["original"]["code"] == row["formatted"]["code"]
        rows.append(row)
        save(
            h.artifacts / "compatibility-progress.json",
            {"changed_paths": changed_paths, "rows": rows},
        )
        print(
            f"{name}: original={row['original']['code']}, formatted={row['formatted']['code']}",
            flush=True,
        )
    # Compare Cargo's native file-mode output to the stdin-based Rust mapping.
    rust_paths = [p for p in h.tracked(original) if p.endswith(".rs")]
    native, _, _ = h.run(["cargo", "fmt", "--all"], cwd=original)
    rust_equal = native["code"] == 0 and h.snapshot(original, rust_paths) == h.snapshot(
        h.candidate, rust_paths
    )
    h.record_phase(
        "compatibility",
        {
            "changed_paths": changed_paths,
            "rows": rows,
            "native_cargo_fmt": native,
            "rust_file_mode_equal": rust_equal,
            "summary": {
                "checks": {
                    r["name"]: {
                        "original": r["original"]["code"],
                        "formatted": r["formatted"]["code"],
                    }
                    for r in rows
                },
                "rust_file_mode_equal": rust_equal,
                "changed_project_files": len(changed_paths),
            },
        },
    )


def hooks(h):
    rows = []
    for arm in ("original", "dprint"):
        repo = clone(h, f"hooks-{arm}")
        save(repo / "dprint.json", config(h))
        if arm == "dprint":
            put(
                repo,
                "lefthook.yml",
                "output: false\nfmt:\n  jobs:\n    - name: dprint\n      run: dprint fmt {files}\npre-commit:\n  jobs:\n    - name: dprint\n      run: dprint fmt {staged_files}\n      stage_fixed: true\n",
            )
        path = Path("packages/web-solid/src/format-eval-hook.ts")
        text = "export const staged={value:1}\n"
        file = put(repo, path, text)
        expected = direct(h, path, text.encode(), repo=repo)[1]
        cmd, _, stderr = h.run(
            ["pnpm", "exec", "lefthook", "run", "fmt", "--file", file], cwd=repo
        )
        rows.append(
            {
                "arm": arm,
                "case": "per-file",
                "command": cmd,
                "formatted": file.read_bytes() == expected,
                "diagnostic": stderr.decode()[:1000],
            }
        )
        file.write_text(text)
        h.require(["git", "add", "--", path], cwd=repo)
        file.write_text(text + "export const unstaged={value:2}\n")
        cmd, _, stderr = h.run(
            ["pnpm", "exec", "lefthook", "run", "pre-commit"], cwd=repo
        )
        index = h.require(["git", "show", f":{path}"], cwd=repo)
        rows.append(
            {
                "arm": arm,
                "case": "partially-staged",
                "command": cmd,
                "index_formatted": index == expected,
                "unstaged_not_in_index": b"unstaged" not in index,
                "unstaged_preserved_in_worktree": b"unstaged" in file.read_bytes(),
                "diagnostic": stderr.decode()[:1000],
            }
        )
        # Actual existing agent hook contract: its exit status hides formatter errors.
        invalid = put(repo, path, "export const = {\n")
        payload = json.dumps({"tool_input": {"file_path": str(invalid)}}).encode()
        cmd, _, _ = h.run(
            ["bash", ".claude/hooks/lefthook-fmt.sh"],
            cwd=repo,
            data=payload,
            env={**h.env, "CLAUDE_PROJECT_DIR": str(repo)},
        )
        verify, _, _ = h.dprint("check", invalid, cwd=repo)
        rows.append(
            {
                "arm": arm,
                "case": "agent-hook-invalid-input",
                "hook": cmd,
                "explicit_check": verify,
                "failure_hidden_by_hook": cmd["code"] == 0 and verify["code"] != 0,
            }
        )
    h.record_phase(
        "hooks",
        {
            "rows": rows,
            "summary": {
                "cases": [
                    {
                        k: v
                        for k, v in r.items()
                        if k not in ("command", "diagnostic", "hook", "explicit_check")
                    }
                    for r in rows
                ]
            },
        },
    )


def rust_compatibility(h):
    # Repair the pilot's missing Cargo subcommand proxies in the isolated PATH.
    for name in ("rustdoc", "cargo-fmt", "cargo-clippy", "clippy-driver"):
        proxy = h.tools / "bin" / name
        if not proxy.exists():
            proxy.symlink_to("rustup")
    rows = []
    for name, command in (
        ("format", ["cargo", "fmt", "--all", "--", "--check"]),
        (
            "clippy",
            ["cargo", "clippy", "--workspace", "--all-targets", "--", "-D", "warnings"],
        ),
        ("tests", ["cargo", "test", "--workspace"]),
    ):
        row: dict = {"name": name}
        for arm in ("original", "formatted"):
            repo = h.root / f"compatibility-{arm}"
            cmd, out, err = h.run(
                command, cwd=repo, timeout=900, label=f"rust-{arm}-{name}"
            )
            row[arm] = cmd
            row[arm + "_diagnostic"] = (out + err).decode(errors="replace")[-2500:]
        rows.append(row)
        print(
            f"{name}: original={row['original']['code']}, formatted={row['formatted']['code']}",
            flush=True,
        )
    original = h.root / "compatibility-original"
    cmd, _, _ = h.run(["cargo", "fmt", "--all"], cwd=original)
    paths = [p for p in h.tracked(original) if p.endswith(".rs")]
    equal = cmd["code"] == 0 and h.snapshot(original, paths) == h.snapshot(
        h.candidate, paths
    )
    h.record_phase(
        "rust-compatibility",
        {
            "rows": rows,
            "native_fmt": cmd,
            "rust_file_mode_equal": equal,
            "summary": {
                "checks": {
                    r["name"]: {a: r[a]["code"] for a in ("original", "formatted")}
                    for r in rows
                },
                "rust_file_mode_equal": equal,
            },
        },
    )


def editor_cases(h, repo, mode, representative=False):
    cases = []
    if representative:
        for name, original in representative_inputs(h).items():
            path = fixture_path("editor-real", name)
            text = original.decode() + "\n\n"
            file = put(repo, path, "\n")
            command, expected, _ = direct(h, path, text.encode(), repo=repo)
            assert command["code"] == 0
            prefix = (
                "<!-- sample INDEX -->\n\n"
                if name.endswith(".md")
                else "// sample INDEX\n"
            )
            cases.append(
                {
                    "name": name,
                    "path": str(file),
                    "input": text,
                    "expected": expected.decode(),
                    "prefix": prefix,
                    "benchmark": True,
                }
            )
        cache_file = put(repo, fixture_path("editor-real", "cache/input.ts"), "\n")
        return {
            "cases": cases,
            "cache_case": {
                "path": str(cache_file),
                "config_path": str(cache_file.parent / ".prettierrc.json"),
                "input": 'const message="hello";\n',
            },
        }
    names = (
        ("basic.md", "basic.tsx", "basic.css", "toc.md")
        if mode.startswith("baseline")
        else (
            "basic.rs",
            "basic.md",
            "basic.tsx",
            "basic.css",
            "basic.py",
            "basic.tf",
            "toc.md",
        )
    )
    for name in names:
        path = fixture_path("editor", name)
        text = samples()[name]
        file = put(repo, path, "\n")
        cmd, expected, _ = direct(h, path, text.encode(), repo=repo)
        assert cmd["code"] == 0
        prefix = (
            "<!-- sample INDEX -->\n\n"
            if name.endswith(".md")
            else ("# sample INDEX\n" if name.endswith(".py") else "// sample INDEX\n")
        )
        cases.append(
            {
                "name": name,
                "path": str(file),
                "input": text,
                "expected": expected.decode(),
                "prefix": prefix,
                "benchmark": name
                in ("basic.rs", "basic.md", "basic.tsx", "basic.py", "basic.tf"),
            }
        )
    if not mode.startswith("baseline"):
        path = fixture_path("editor", "invalid.ts")
        cases.append(
            {
                "name": "invalid.ts",
                "path": str(put(repo, path, "\n")),
                "input": "const = {\n",
                "expected": "const = {\n",
                "benchmark": False,
                "invalid": True,
            }
        )
    return {"cases": cases}


def prepare_editors(h):
    base = h.root / "editors"
    base.mkdir(exist_ok=True)
    editor_tools = base / "tools"
    editor_tools.mkdir(exist_ok=True)
    if not (editor_tools / "node_modules").exists():
        save(
            editor_tools / "package.json",
            {
                "private": True,
                "dependencies": {"prettier": "3.9.6", "markdown-toc": "1.2.0"},
            },
        )
        h.require(
            [
                "pnpm",
                "install",
                "--ignore-scripts",
                "--store-dir",
                h.root / "environments/pnpm-store",
            ],
            cwd=editor_tools,
            timeout=180,
        )
    for name, target in (
        ("prettier", editor_tools / "node_modules/prettier/bin/prettier.cjs"),
        ("markdown-toc", editor_tools / "node_modules/markdown-toc/cli.js"),
    ):
        link = h.tools / "bin" / name
        if not link.exists():
            link.symlink_to(target)
    extension_dir = base / "vscode-extensions"
    extension_dir.mkdir(exist_ok=True)
    for name in (
        "esbenp.prettier-vscode-12.4.0",
        "yzhang.markdown-all-in-one-3.6.3",
        "dbaeumer.vscode-eslint-3.0.34",
        "stylelint.vscode-stylelint-2.2.1",
        "hashicorp.hcl-0.6.0",
    ):
        target = extension_dir / name
        if not target.exists():
            shutil.copytree(Path.home() / ".vscode/extensions" / name, target)
    install_profile = base / "vscode-install"
    install_profile.mkdir(exist_ok=True)
    if not list(extension_dir.glob("dprint.dprint-*")):
        h.require(
            [
                h.manifest["host_binaries"]["code"],
                "--user-data-dir",
                install_profile,
                "--extensions-dir",
                extension_dir,
                "--install-extension",
                "dprint.dprint@0.17.2",
            ],
            timeout=180,
            cwd=base,
            label="vscode-install",
        )
    development = base / "vscode-test-extension"
    save(
        development / "package.json",
        {
            "name": "formatting-evaluation",
            "publisher": "local",
            "version": "0.0.1",
            "engines": {"vscode": "^1.80.0"},
        },
    )
    return base


def nvim_run(h, base, mode, representative=False):
    from experiments import distribution

    repo = clone(h, f"editor-nvim-{mode}")
    save(repo / "dprint.json", config(h))
    profile = base / repo.name.removeprefix("editor-")
    profile.mkdir()
    for source, destination in (
        (Path.home() / ".config/nvim", profile / "config/nvim"),
        (Path.home() / ".local/share/nvim/lazy", profile / "data/nvim/lazy"),
        (Path.home() / ".local/share/nvim/mason", profile / "data/nvim/mason"),
        (Path.home() / ".local/share/nvim/site", profile / "data/nvim/site"),
    ):
        shutil.copytree(source, destination, symlinks=True)
        for link in destination.rglob("*"):
            if link.is_symlink():
                target = link.readlink()
                if target.is_absolute() and target.is_relative_to(source):
                    link.unlink()
                    link.symlink_to(destination / target.relative_to(source))
    put(
        profile,
        "bootstrap.lua",
        """vim.opt.rtp:prepend(vim.env.XDG_DATA_HOME .. "/nvim/lazy/lazy.nvim")
local lazy = require("lazy")
local setup = lazy.setup
lazy.setup = function(opts)
  opts.checker = { enabled = false }
  opts.change_detection = { enabled = false }
  opts.install = { missing = false }
  return setup(opts)
end
dofile(vim.env.XDG_CONFIG_HOME .. "/nvim/init.lua")
""",
    )
    put(
        profile,
        "config/nvim/lua/plugins/zz-eval-support.lua",
        """return {
  { "nvim-treesitter/nvim-treesitter", opts = { auto_install = false } },
}
""",
    )
    if mode != "baseline":
        put(
            profile,
            "config/nvim/lua/plugins/zz-format-eval.lua",
            """return {
  { "stevearc/conform.nvim", opts = function(_, opts)
      for _, ft in ipairs({"rust", "markdown", "markdown.mdx", "typescript", "typescriptreact", "css", "python", "terraform", "tf", "hcl"}) do
        opts.formatters_by_ft[ft] = { "dprint" }
      end
      if vim.env.FORMAT_EVAL_MODE == "integrated" then
        opts.formatters_by_ft.markdown = { "dprint", "markdown-toc" }
      end
      opts.default_format_opts.lsp_format = "never"
    end },
}
""",
        )
    spec = editor_cases(h, repo, mode, representative=representative)
    save(profile / "cases.json", spec)
    output = profile / "result.json"
    env = {
        **h.env,
        "XDG_CONFIG_HOME": str(profile / "config"),
        "XDG_DATA_HOME": str(profile / "data"),
        "XDG_STATE_HOME": str(profile / "state"),
        "XDG_CACHE_HOME": str(profile / "cache"),
        "FORMAT_EVAL_MODE": mode,
        "FORMAT_EVAL_CASES": str(profile / "cases.json"),
        "FORMAT_EVAL_OUTPUT": str(output),
    }
    cmd, _, _ = h.run(
        [
            h.manifest["host_binaries"]["nvim"],
            "--headless",
            "-u",
            profile / "bootstrap.lua",
            "+lua dofile(" + json.dumps(str(HERE / "nvim_save.lua")) + ")",
        ],
        cwd=repo,
        env=env,
        timeout=180,
        label=f"nvim-{mode}",
    )
    result = (
        json.loads(output.read_text())
        if output.exists()
        else {"ok": False, "error": "No editor result produced"}
    )
    for row in result.get("cases", []):
        if row.get("samples_ms"):
            row["timing"] = distribution(row["samples_ms"])
    return {"mode": mode, "command": cmd, "result": result}


def vscode_run(h, base, mode, workspace=False, representative=False):
    from experiments import distribution

    suffix = "-workspace" if workspace else ""
    repo = clone(h, f"editor-vscode-{mode}{suffix}")
    save(repo / "dprint.json", config(h))
    # macOS Unix sockets reject VS Code's normal long temporary profile path.
    profile = h.root.parent / ("v-" + digest(str(repo).encode())[:6])
    profile.mkdir()
    formatter = (
        "esbenp.prettier-vscode" if mode.startswith("baseline") else "dprint.dprint"
    )
    formatting_settings = {
        "editor.formatOnSave": True,
        "editor.codeActionsOnSave": {"source.fixAll": "explicit"}
        if mode in ("integrated", "baseline-integrated")
        else {},
        "markdown.extension.toc.updateOnSave": mode != "dprint",
        "editor.defaultFormatter": formatter,
        **{
            f"[{language}]": {
                "editor.defaultFormatter": formatter,
                "editor.formatOnSave": True,
            }
            for language in (
                "rust",
                "markdown",
                "typescript",
                "typescriptreact",
                "css",
                "python",
                "terraform",
                "hcl",
                "plaintext",
            )
        },
    }
    for folder in (repo, repo / "packages/web-solid", repo / "terraform"):
        save(folder / ".vscode/settings.json", formatting_settings)
    if workspace:
        put(repo, "evaluation.code-workspace", (repo / ".code-workspace").read_bytes())
    save(
        profile / "User/settings.json",
        {
            "telemetry.telemetryLevel": "off",
            "update.mode": "none",
            "extensions.autoUpdate": False,
            "extensions.autoCheckUpdates": False,
            "security.workspace.trust.enabled": False,
            "git.enabled": False,
            "editor.formatOnSave": True,
            "dprint.path": str(h.tools / "bin/dprint"),
            "dprint.verbose": True,
        },
    )
    save(
        profile / "cases.json",
        editor_cases(h, repo, mode, representative=representative),
    )
    output = profile / "result.json"
    env = {
        **h.env,
        "FORMAT_EVAL_MODE": mode,
        "FORMAT_EVAL_CASES": str(profile / "cases.json"),
        "FORMAT_EVAL_OUTPUT": str(output),
        "FORMAT_EVAL_DPRINT": str(h.tools / "bin/dprint"),
    }
    binary = (
        Path(h.manifest["host_binaries"]["code"]).resolve().parents[3] / "MacOS/Code"
    )
    cmd, _, _ = h.run(
        [
            binary,
            "--user-data-dir",
            profile,
            "--extensions-dir",
            base / "vscode-extensions",
            "--extensionDevelopmentPath=" + str(base / "vscode-test-extension"),
            "--extensionTestsPath=" + str(HERE / "vscode_save.cjs"),
            "--disable-workspace-trust",
            "--skip-welcome",
            "--skip-release-notes",
            "--disable-updates",
            "--disable-telemetry",
            repo / "evaluation.code-workspace" if workspace else repo,
        ],
        cwd=repo,
        env=env,
        timeout=240,
        label=f"vscode-{mode}{suffix}",
    )
    result = (
        json.loads(output.read_text())
        if output.exists()
        else {"ok": False, "error": "No editor result produced"}
    )
    for row in result.get("cases", []):
        if row.get("samples_ms"):
            row["timing"] = distribution(row["samples_ms"])
    return {"mode": mode + suffix, "command": cmd, "result": result}


def editors(h):
    base = prepare_editors(h)
    progress = h.artifacts / "editors-progress.json"
    if progress.exists():
        attempt = 1
        while (h.artifacts / f"editors-pilot-{attempt}.json").exists():
            attempt += 1
        shutil.copy2(progress, h.artifacts / f"editors-pilot-{attempt}.json")
    rows = []
    for editor, function in (("nvim", nvim_run), ("vscode", vscode_run)):
        for mode in ("baseline", "dprint", "integrated"):
            row = {"editor": editor, **function(h, base, mode)}
            rows.append(row)
            save(h.artifacts / "editors-progress.json", {"rows": rows})
            print(f"{editor}/{mode}: {row['result']['ok']}", flush=True)
    rows.append({"editor": "vscode", **vscode_run(h, base, "dprint", workspace=True)})
    summary = [
        {
            "editor": r["editor"],
            "mode": r["mode"],
            "ok": r["result"]["ok"],
            "cases": [
                {
                    k: c[k]
                    for k in ("name", "equals_direct", "stable", "timing")
                    if k in c
                }
                for c in r["result"].get("cases", [])
            ],
        }
        for r in rows
    ]
    h.record_phase("editors", {"rows": rows, "summary": {"profiles": summary}})


def vscode(h):
    base = prepare_editors(h)
    previous = json.loads((h.artifacts / "editors.json").read_text())
    rows = [r for r in previous["rows"] if r["editor"] == "nvim"]
    for mode, workspace in (
        ("baseline", False),
        ("dprint", False),
        ("integrated", False),
        ("dprint", True),
    ):
        row = {"editor": "vscode", **vscode_run(h, base, mode, workspace=workspace)}
        rows.append(row)
        save(h.artifacts / "vscode-progress.json", {"rows": rows})
        print(f"vscode/{row['mode']}: {row['result']['ok']}", flush=True)
    summary = [
        {
            "editor": r["editor"],
            "mode": r["mode"],
            "ok": r["result"]["ok"],
            "cases": [
                {
                    k: c[k]
                    for k in ("name", "equals_direct", "stable", "timing")
                    if k in c
                }
                for c in r["result"].get("cases", [])
            ],
        }
        for r in rows
    ]
    h.record_phase("editors", {"rows": rows, "summary": {"profiles": summary}})


def representative_inputs(h):
    corpus = json.loads((h.artifacts / "corpus.json").read_text())["rows"]
    result = {}
    for extension in (".rs", ".tsx", ".md"):
        eligible = sorted(
            (
                r
                for r in corpus
                if r["path"].endswith(extension) and "format-eval" not in r["path"]
            ),
            key=lambda r: r["bytes"],
        )
        for size, row in (
            ("median", eligible[len(eligible) // 2]),
            ("largest", eligible[-1]),
        ):
            data = h.require(["git", "show", f"{COMMIT}:{row['path']}"], cwd=h.baseline)
            result[size + extension] = data
    return result


def representative(h):
    from experiments import distribution

    base = prepare_editors(h)
    inputs = representative_inputs(h)
    timings = {}
    rows = []
    for name, source in inputs.items():
        path = fixture_path("representative", name)
        file = put(h.candidate, path, source)
        values = {"direct": [], "dprint": []}
        prefix = (
            "<!-- sample INDEX -->\n\n" if name.endswith(".md") else "// sample INDEX\n"
        )
        for i in range(105):
            data = prefix.replace("INDEX", str(i)).encode() + source + b"\n\n"
            pair = {}
            for arm in ("direct", "dprint") if i % 2 else ("dprint", "direct"):
                command, output, _ = (
                    direct(h, path, data)
                    if arm == "direct"
                    else h.dprint("fmt", "--stdin", file, data=data)
                )
                assert command["code"] == 0
                pair[arm] = output
                if i >= 5:
                    values[arm].append(command["ms"])
                    rows.append({"name": name, "arm": arm, "command": command})
            assert pair["direct"] == pair["dprint"] and data != pair["dprint"]
        timings[name] = {
            "bytes": len(source),
            **{arm: distribution(value) for arm, value in values.items()},
        }
    editor_rows = []
    for editor, function in (("nvim", nvim_run), ("vscode", vscode_run)):
        row = {"editor": editor, **function(h, base, "dprint", representative=True)}
        editor_rows.append(row)
        save(
            h.artifacts / "representative-progress.json",
            {"timing": timings, "editors": editor_rows},
        )
    integrated = vscode_run(h, base, "integrated")
    h.record_phase(
        "representative",
        {
            "rows": rows,
            "timing": timings,
            "editors": editor_rows,
            "integrated_followup": integrated,
            "summary": {
                "cli": timings,
                "editor_profiles": [
                    {
                        "editor": r["editor"],
                        "ok": r["result"]["ok"],
                        "external_config_refresh": r["result"].get(
                            "external_config_refresh"
                        ),
                        "cases": [
                            {
                                k: c[k]
                                for k in ("name", "equals_direct", "stable", "timing")
                                if k in c
                            }
                            for c in r["result"].get("cases", [])
                        ],
                    }
                    for r in editor_rows
                ],
                "integrated_followup": {
                    "ok": integrated["result"]["ok"],
                    "cases": [
                        {
                            k: c[k]
                            for k in (
                                "name",
                                "saved",
                                "equals_direct",
                                "second_saved",
                                "second_equals_direct",
                                "stable",
                            )
                            if k in c
                        }
                        for c in integrated["result"].get("cases", [])
                    ],
                },
            },
        },
    )


def example(h):
    source = (
        HERE.parents[1]
        / "skills/engineering-standard/references/formatting/dprint.example.json"
    )
    repo = clone(h, "final-example")
    put(repo, "dprint.json", source.read_bytes())
    h.require(
        ["uv", "sync", "--locked", "--only-dev", "--no-install-workspace"],
        cwd=repo,
        timeout=180,
    )
    paths = [
        str(Path(p).relative_to(repo))
        for p in h.require(["dprint", "output-file-paths"], cwd=repo)
        .decode()
        .splitlines()
    ]
    before = h.snapshot(repo)
    initial, _, _ = h.dprint("check", "--list-different", cwd=repo)
    check_preserved = before == h.snapshot(repo)
    formatted, _, _ = h.dprint("fmt", cwd=repo)
    after = h.snapshot(repo)
    verified, _, _ = h.dprint("check", "--list-different", cwd=repo)
    again, _, _ = h.dprint("fmt", cwd=repo)
    matches = h.snapshot(repo, paths) == h.snapshot(h.candidate, paths)
    result = {
        "example_sha256": digest(source.read_bytes()),
        "files": len(paths),
        "initial_check": initial,
        "format": formatted,
        "final_check": verified,
        "repeat": again,
        "check_preserved": check_preserved,
        "matches_evaluated_output": matches,
        "idempotent": after == h.snapshot(repo),
    }
    h.record_phase("example", result)


def editor_actions(h):
    base = prepare_editors(h)
    baseline = vscode_run(h, base, "baseline-integrated")
    candidate = vscode_run(h, base, "integrated")
    h.record_phase(
        "editor-actions",
        {
            "baseline": baseline,
            "candidate": candidate,
            "summary": {
                arm: [
                    {
                        k: c[k]
                        for k in (
                            "name",
                            "saved",
                            "equals_direct",
                            "second_saved",
                            "second_equals_direct",
                            "stable",
                        )
                        if k in c
                    }
                    for c in row["result"].get("cases", [])
                ]
                for arm, row in (("baseline", baseline), ("candidate", candidate))
            },
        },
    )
