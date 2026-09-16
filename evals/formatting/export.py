"""Export portable evidence without embedding the evaluated project's source text."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from experiments import config
from harness import COMMIT, HERE, digest, save

PHASES = (
    "setup",
    "pilot",
    "corpus",
    "behavior",
    "timing",
    "compatibility",
    "rust-compatibility",
    "hooks",
    "editors",
    "representative",
    "extensions",
    "example",
    "editor-actions",
)


def export(h, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    phases = {
        name: json.loads((h.artifacts / f"{name}.json").read_text())
        for name in PHASES
        if name != "rust-compatibility" or (h.artifacts / f"{name}.json").exists()
    }
    guard = h.source_guard()
    assert all(guard.values())

    def portable(value):
        if isinstance(value, str):
            return (
                value.replace(str(h.root), "$EVAL_ROOT")
                .replace(str(h.root.parent), "$TEMP_ROOT")
                .replace(str(HERE), "$HARNESS")
                .replace(str(Path.home()), "$HOME")
            )
        if isinstance(value, list):
            return [portable(item) for item in value]
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if key in (
                    "output",
                    "second_output",
                    "buffer_after_first_save",
                    "text",
                ) and isinstance(item, str):
                    result[key + "_sha256"] = digest(item.encode())
                    result[key + "_bytes"] = len(item.encode())
                elif key == "samples_ms":
                    continue  # Raw measurements are retained once, in timings.csv.
                elif key.endswith("_diagnostic"):
                    result[key + "_sha256"] = digest(item.encode())
                else:
                    result[key] = portable(item)
            return result
        return value

    corpus = phases["corpus"]
    rows = [
        {
            "path": row["path"],
            "bytes": row["bytes"],
            "input_sha256": row["input_sha256"],
            "direct_sha256": row["direct_sha256"],
            "candidate_sha256": row["candidate_sha256"],
            "direct_exit": row["direct"]["code"],
            "candidate_exit": row["candidate"]["code"],
            "idempotent": row["idempotent"],
            "changed": row["changed"],
        }
        for row in corpus["rows"]
    ]
    save(output / "corpus.json", rows)
    with (output / "timings.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["suite", "case", "entry_point", "sample", "ms"])
        for suite in ("timing", "representative"):
            counts = {}
            for row in phases[suite]["rows"]:
                case = row.get("case", row.get("name"))
                key = (case, row["arm"])
                index = counts.get(key, 0)
                counts[key] = index + 1
                writer.writerow(
                    [suite, case, row["arm"], index, f"{row['command']['ms']:.6f}"]
                )
        for case, values in phases["timing"]["cache"].items():
            for index, ms in enumerate(values["samples_ms"]):
                writer.writerow(["unchanged-check", case, "dprint", index, f"{ms:.6f}"])
        for suite, profiles in (
            ("editors", phases["editors"]["rows"]),
            ("representative", phases["representative"]["editors"]),
        ):
            for profile in profiles:
                for case in profile["result"].get("cases", []):
                    for index, ms in enumerate(case.get("samples_ms", [])):
                        writer.writerow(
                            [
                                suite,
                                case["name"],
                                f"{profile['editor']}/{profile['mode']}",
                                index,
                                f"{ms:.6f}",
                            ]
                        )
    evidence = {}
    for name, phase in phases.items():
        selected = dict(phase)
        if name in ("corpus", "timing", "representative"):
            selected.pop("rows", None)
        if name == "corpus":
            for key in ("check_before", "bulk", "final_check", "bulk_second"):
                selected[key] = {k: v for k, v in selected[key].items() if k != "args"}
        if name == "timing":
            for key in ("bulk_incremental_False", "bulk_incremental_True"):
                selected[key] = [
                    {k: v for k, v in row.items() if k != "args"}
                    for row in selected[key]
                ]
        if name == "compatibility" and selected["native_cargo_fmt"]["code"] != 0:
            selected["rust_file_mode_equal"] = None
            selected["rust_evidence_invalidated"] = (
                "Missing isolated Cargo proxies; superseded by rust-compatibility."
            )
        evidence[name] = portable(selected)
    save(output / "evidence.json", evidence)
    representative = phases["representative"]["summary"]
    compatibility = json.loads(json.dumps(phases["compatibility"]["summary"]))
    if "rust-compatibility" in phases:
        corrected = phases["rust-compatibility"]["summary"]
        for name in ("format", "clippy", "tests"):
            compatibility["checks"][f"rust-{name}"] = corrected["checks"][name]
        compatibility["rust_file_mode_equal"] = corrected["rust_file_mode_equal"]
    summary = {
        "decision": "Adopt conditional workflow guidance and a minimal stdin-only configuration pattern; unconditional exec rollout fails process-lifecycle and combined-save gates.",
        "corpus": {
            k: corpus[k]
            for k in (
                "counts",
                "files",
                "changed",
                "mismatches",
                "errors",
                "non_idempotent",
                "check_preserved",
                "bulk_matches_stdin",
                "bulk_idempotent",
            )
        },
        "project_files": sum("format-eval" not in r["path"] for r in rows),
        "synthetic_files": sum("format-eval" in r["path"] for r in rows),
        "check_before_exit": corpus["check_before"]["code"],
        "check_after_exit": corpus["final_check"]["code"],
        "behavior": phases["behavior"]["summary"],
        "hooks": phases["hooks"]["summary"],
        "compatibility": compatibility,
        "changed_project_files": phases["compatibility"]["changed_paths"],
        "small_fixture_latency": phases["timing"]["summary"],
        "representative_latency": representative,
        "extensions": phases["extensions"]["summary"],
        "example": {
            k: phases["example"][k]
            for k in (
                "example_sha256",
                "files",
                "check_preserved",
                "matches_evaluated_output",
                "idempotent",
            )
        },
        "save_actions_followup": phases["editor-actions"]["summary"],
        "source_guard": guard,
    }
    save(output / "summary.json", portable(summary))
    system = (
        h.require(
            ["sysctl", "-n", "hw.model", "machdep.cpu.brand_string", "hw.memsize"]
        )
        .decode()
        .splitlines()
    )
    editor_versions = {
        "nvim": h.require([h.manifest["host_binaries"]["nvim"], "--version"])
        .decode()
        .splitlines()[0],
        "vscode": h.require([h.manifest["host_binaries"]["code"], "--version"])
        .decode()
        .splitlines(),
    }
    plugin_commits = {}
    nvim = next(
        row
        for row in phases["editors"]["rows"]
        if row["editor"] == "nvim" and row["mode"] == "dprint"
    )
    nvim_profile = Path(
        nvim["command"]["args"][nvim["command"]["args"].index("-u") + 1]
    ).parent
    for name in ("LazyVim", "lazy.nvim", "conform.nvim"):
        plugin_commits[name] = (
            h.require(
                ["git", "rev-parse", "HEAD"],
                cwd=nvim_profile / "data/nvim/lazy" / name,
            )
            .decode()
            .strip()
        )
    manifest = {
        "schema_version": 1,
        "source_repository": "https://github.com/46ki75/internal",
        "source_commit": COMMIT,
        "versions": h.manifest["versions"],
        "editor_versions": editor_versions,
        "nvim_plugin_commits": plugin_commits,
        "platform": h.manifest["platform"],
        "hardware": system,
        "plugin": h.manifest["plugin"],
        "downloads": h.manifest["downloads"],
        "configuration": config(h),
        "source_configuration_sha256": {
            p: h.manifest["snapshot_hashes"][p]
            for p in (
                "package.json",
                "pnpm-lock.yaml",
                "Cargo.toml",
                "Cargo.lock",
                "rust-toolchain.toml",
                "pyproject.toml",
                "uv.lock",
                "packages/web-solid/package.json",
                "packages/web-solid/.prettierignore",
                ".markdownlint-cli2.yaml",
                "lefthook.yml",
            )
        },
        "harness_sha256": {
            p.name: digest(p.read_bytes())
            for p in HERE.iterdir()
            if p.suffix in (".py", ".lua", ".cjs", ".json") or p.name == "rule.md"
        },
        "artifact_sha256": {
            p.name: digest(p.read_bytes())
            for p in output.iterdir()
            if p.name
            in (
                "summary.json",
                "evidence.json",
                "corpus.json",
                "timings.csv",
                "usability.json",
            )
        },
        "calibration_artifact_sha256": {
            p.name: digest(p.read_bytes())
            for p in h.artifacts.iterdir()
            if p.suffix == ".json" and ("attempt" in p.name or "pilot-" in p.name)
        },
        "limitations": [
            "One macOS arm64 host; no Windows/Linux execution.",
            "CLI/Neovim/VScode save trials use real formatters; Neovim runs headless with the UIEnter startup event explicitly fired.",
            "VS Code uses formatting-focused isolated profiles; its full personal extension set was not copied.",
            "Combined-save cancellation is a reproduced observation; the responsible extension was not isolated.",
            "Agent usability trials are text-only command planning, not autonomous tool-use or a statistical efficacy study.",
        ],
    }
    save(output / "manifest.json", portable(manifest))
    print(
        json.dumps(
            {
                "output": str(output),
                "project_files": summary["project_files"],
                "synthetic_files": summary["synthetic_files"],
                "source_guard": guard,
            },
            indent=2,
        )
    )
