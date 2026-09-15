#!/usr/bin/env python3
"""Summarize recorded calibration evidence without making model calls."""

import argparse
from collections import Counter
import json
from pathlib import Path


def load(path):
    return json.loads(path.read_text())


def analyze(output):
    manifest = load(output / "manifest.json")
    summary = load(output / "summary.json")
    counts = {"requirements": Counter(), "issues": Counter(), "regressions": Counter()}
    flags, invalid, checks, clean = [], [], [], []
    for folder in sorted((output / "judges").iterdir()):
        if not folder.is_dir() or not (folder / "result.json").exists():
            continue
        result = load(folder / "result.json")
        if result["status"] != "completed":
            record = {"trial": folder.name, "failures": result["failures"]}
            try:
                value = load(folder / "output.md")
                record["root_keys"] = sorted(value)
                record["candidate_keys"] = sorted(value.get("candidates", {}))
            except (ValueError, TypeError, AttributeError):
                record["json_parseable"] = False
            invalid.append(record)
            continue
        value = load(folder / "judgment.json")
        mapping = load(folder / "mapping.json")
        for side, assessment in value["candidates"].items():
            for kind in ("requirements", "issues"):
                counts[kind].update(item["status"] for item in assessment[kind])
            for item in assessment["regressions"]:
                counts["regressions"][item["severity"]] += 1
                flags.append({"trial": folder.name, "arm": mapping[side], **item})
    for case in manifest["inputs"]["cases"]:
        for arm in ("A", "B", "C"):
            folder = output / "writers" / (case["id"] + "-" + arm)
            if not (folder / "checks.json").exists():
                continue
            checks.extend(load(folder / "checks.json"))
            if not case["issues"]:
                text = (folder / "output.md").read_bytes().decode("utf-8")
                clean.append(
                    {
                        "case": case["id"],
                        "arm": arm,
                        "exactly_equal": text == case["draft"],
                        "equal_ignoring_final_newline": text.rstrip("\n")
                        == case["draft"].rstrip("\n"),
                    }
                )
    complete = [p for p in summary["comparisons"] if len(p["votes"]) == 2]
    incomplete = [
        p["case"] + ":" + p["pair"]
        for p in summary["comparisons"]
        if len(p["votes"]) < 2
    ]
    usage = summary["usage"]
    total_tokens = sum(sum(role["tokens"].values()) for role in usage.values())
    projection = summary["full_suite_projection"]
    full_tokens = sum(sum(role["tokens"].values()) for role in projection.values())
    serial_hours = sum(role["serial_hours"] for role in projection.values())
    return {
        "scope": "Descriptive calibration analysis. Repeated judgments are dependent observations.",
        "mechanical_checks": {
            "passed": sum(c["passed"] for c in checks),
            "total": len(checks),
        },
        "valid_judge_annotations_not_unique_outputs": {
            key: dict(value) for key, value in counts.items()
        },
        "judge_regression_flags_not_adjudicated": flags,
        "invalid_judgments_excluded_from_votes": invalid,
        "order_comparisons": {
            "complete": len(complete),
            "agree": sum(p["order_agrees"] for p in complete),
            "disagree": sum(not p["order_agrees"] for p in complete),
            "incomplete": incomplete,
        },
        "clean_control": clean,
        "usage": {
            "experimental_sessions": sum(role["sessions"] for role in usage.values()),
            "reported_tokens_all_buckets": total_tokens,
            "reported_writer_cost": usage["writers"]["reported_cost"],
            "reported_judge_cost": usage["judges"]["reported_cost"],
        },
        "projection": {
            "writer_sessions": 324,
            "judge_sessions": 270,
            "reported_tokens_all_buckets": full_tokens,
            "serial_hours": serial_hours,
            "ideal_hours_at_concurrency_3": serial_hours / 3,
            "reported_judge_cost": projection["judges"][
                "reported_cost_projection_not_billing"
            ],
            "writer_billable_cost": "unknown; reported OAuth cost is zero",
            "exclusions": "Authoring, dataset construction, analysis, retries, and provider-unreported usage",
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    directory = parser.parse_args().output.resolve()
    result = analyze(directory)
    serialized = json.dumps(result, indent=2) + "\n"
    (directory / "analysis.json").write_text(serialized)
    print(serialized)
