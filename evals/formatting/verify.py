#!/usr/bin/env python3
"""Offline consistency checks for the retained formatting evidence and its claims."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shlex
from collections import defaultdict
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(result_dir):
    def load(name):
        return json.loads((result_dir / name).read_text())

    manifest, summary, evidence = [
        load(name) for name in ("manifest.json", "summary.json", "evidence.json")
    ]
    for name, expected in manifest["artifact_sha256"].items():
        assert sha(result_dir / name) == expected, f"Changed artifact: {name}"
    corpus = load("corpus.json")
    assert len(corpus) == summary["corpus"]["files"] == 283
    assert summary["project_files"] == 263 and summary["synthetic_files"] == 20
    assert len({r["path"] for r in corpus}) == len(corpus)
    assert sum(r["changed"] for r in corpus) == 22
    for row in corpus:
        assert row["direct_exit"] == row["candidate_exit"] == 0
        assert row["direct_sha256"] == row["candidate_sha256"]
        assert row["idempotent"]
    assert summary["check_before_exit"] == 20 and summary["check_after_exit"] == 0
    for key in ("check_preserved", "bulk_matches_stdin", "bulk_idempotent"):
        assert summary["corpus"][key]
    assert all(summary["source_guard"].values())
    example = (
        Path(__file__).resolve().parents[2]
        / "skills/engineering-standard/references/formatting/dprint.example.json"
    )
    assert sha(example) == summary["example"]["example_sha256"]
    assert summary["example"]["files"] == 263
    assert (
        summary["example"]["check_preserved"]
        and summary["example"]["matches_evaluated_output"]
        and summary["example"]["idempotent"]
    )
    assert (
        evidence["example"]["format"]["code"]
        == evidence["example"]["final_check"]["code"]
        == 0
    )

    # These failures are part of the conclusion; do not silently turn them into passes.
    assert summary["behavior"]["unexpected_results"] == ["signal-visible"]
    assert (
        summary["behavior"]["timeout_child_alive"]
        and summary["behavior"]["timeout_child_completed"]
    )
    assert summary["behavior"]["cache_agreement"] == {
        "no-keys": False,
        "keys": True,
        "disabled": True,
    }
    assert summary["extensions"]["unsafe_file_writer_mutates_check"]
    assert summary["extensions"]["cancellation_child_completed"]
    assert not summary["extensions"]["markdownlint_mismatches"]
    assert summary["extensions"]["markdownlint_cases"] == 14
    assert summary["extensions"]["markdown_engine_differences"] == 5
    assert (
        not summary["extensions"]["selection_failures"]
        and summary["extensions"]["uv_equal"]
    )

    for profile in evidence["editors"]["rows"]:
        assert profile["result"]["ok"], (profile["editor"], profile["mode"])
        if profile["mode"] in ("dprint", "dprint-workspace"):
            assert all(
                row["equals_direct"] and row["stable"]
                for row in profile["result"]["cases"]
            )
    for profile in evidence["representative"]["editors"]:
        assert profile["result"]["ok"]
        assert all(
            row["equals_direct"] and row["stable"] for row in profile["result"]["cases"]
        )
    assert evidence["representative"]["editors"][1]["result"][
        "external_config_refresh"
    ]["pass"]
    baseline = summary["save_actions_followup"]["baseline"]
    candidate = summary["save_actions_followup"]["candidate"]
    assert all(r["saved"] and r["stable"] for r in baseline)
    assert [r["name"] for r in candidate if not r["saved"]] == ["basic.md", "basic.css"]
    assert all(r["second_saved"] and r["second_equals_direct"] for r in candidate)
    checks = summary["compatibility"]["checks"]
    for name in (
        "rust-format",
        "rust-clippy",
        "rust-tests",
        "web-format",
        "web-eslint",
        "web-types",
        "web-tests",
        "python-lint",
        "terraform-format",
    ):
        assert checks[name] == {"original": 0, "formatted": 0}
    assert checks["python-format"] == {"original": 1, "formatted": 0}
    assert checks["web-stylelint"] == {"original": 2, "formatted": 2}
    assert checks["markdown-lint"] == {"original": 1, "formatted": 1}

    groups = defaultdict(list)
    with (result_dir / "timings.csv").open() as stream:
        for row in csv.DictReader(stream):
            key = (row["suite"], row["case"], row["entry_point"])
            assert int(row["sample"]) == len(groups[key])
            groups[key].append(float(row["ms"]))
    assert len(groups) == 51 and all(len(values) == 100 for values in groups.values())

    def check_stats(key, recorded):
        values = sorted(groups[key])
        p95 = values[math.ceil(len(values) * 0.95) - 1]
        assert recorded["n"] == len(values)
        assert abs(p95 - recorded["p95_ms"]) < 0.00001, key

    for name, row in summary["representative_latency"]["cli"].items():
        for arm in ("direct", "dprint"):
            check_stats(("representative", name, arm), row[arm])
    for profile in summary["representative_latency"]["editor_profiles"]:
        for row in profile["cases"]:
            key = ("representative", row["name"], profile["editor"] + "/dprint")
            check_stats(key, row["timing"])
            assert row["timing"]["p95_ms"] < 500

    usability = load("usability.json")
    counts = {}
    for arm in ("baseline", "candidate"):
        counts[arm] = sum(
            shlex.split(command)[:2] == ["dprint", "check"]
            for row in usability["observations"]
            for command in row[arm + "_commands"]
        )
    assert counts == {"baseline": 0, "candidate": 7}
    root = Path(__file__).resolve().parents[2]
    documents = [
        root / "skills/engineering-standard/SKILL.md",
        root / "skills/engineering-standard/references/formatting/README.md",
        root / "skills/engineering-standard/references/formatting/dprint.md",
        Path(__file__).resolve().parent / "README.md",
        result_dir / "report.md",
    ]
    for document in documents:
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", document.read_text()):
            if "://" not in target:
                assert (document.parent / target.split("#")[0]).exists(), (
                    document,
                    target,
                )
    rule = (Path(__file__).resolve().parent / "rule.md").read_text().strip()
    # The standard now uses Lefthook; retain the evaluated rule in its historical reference.
    reference = documents[2].read_text()
    normalized = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", reference)
    assert rule in normalized, (
        "Historical operational rule differs from the evaluated candidate"
    )
    print(
        "Verified: artifact hashes, 283-file equivalence, published example, recorded failed gates, integration results, and 5,100 timing samples."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results",
        type=Path,
        default=Path(__file__).resolve().parent / "results/2026-09-16",
    )
    verify(parser.parse_args().results)
