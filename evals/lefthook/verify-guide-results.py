#!/usr/bin/env python3
"""Check the portable guide-evaluation evidence without installing native tools."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def verify(root):
    def load(name):
        return json.loads((root / name).read_text())

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    manifest = load("manifest.json")
    results = load("results.json")
    commands = load("commands.json")
    for name, expected in manifest["artifacts"].items():
        assert sha(root / name) == expected, f"Changed artifact: {name}"
    for name, expected in manifest["inputs"].items():
        assert sha(root / "inputs" / name) == expected, f"Changed frozen input: {name}"
    assert results["passed"] and not results["failed_cases"]
    cases = results["results"]
    assert results["cases"] == len(cases)
    assert results["commands"] == len(commands)
    assert results["assertions"] == sum(len(case["assertions"]) for case in cases)
    assert results["hook_invocations"] == sum(
        row["argv"][:4] == ["pnpm", "exec", "lefthook", "run"] for row in commands
    )
    names = {case["name"] for case in cases}
    assert len(names) == len(cases)
    assert {
        "selection-and-native-parity-gobwas",
        "selection-and-native-parity-doublestar",
        "missing-matching-and-nonmatching-paths",
        "installed-partial-staging-success",
        "installed-partial-staging-failure",
        "mutation-wrong-glob",
        "mutation-scope-mismatch",
        "mutation-suppressed-failure",
        "mutation-mutating-check",
        "committed-repository-regression",
        "original-source-preservation",
    } <= names
    for case in cases:
        assert case["passed"] and case["assertions"], case["name"]
        for check in case["assertions"]:
            assert check["passed"], check["description"]
            evidence = check["evidence"]
            if evidence and "changed_files" in evidence:
                assert not evidence["changed_files"]
                assert evidence["before"] == evidence["after"]
            if evidence and "command" in evidence:
                command = commands[evidence["command"]]
                assert command["case"] == case["name"]
                assert command["exit"] == evidence["exit"]
        for index in case.get("commands", []):
            assert commands[index]["case"] == case["name"]
    if (root / "calibration").exists():
        for name, expected in manifest["calibration_artifacts"].items():
            assert sha(root / "calibration" / name) == expected, name
        calibration = load("calibration/results.json")
        assert not calibration["passed"]
        assert calibration["failed_cases"] == [
            "skip-missing.py",
            "committed-repository-regression",
        ]
        old_manifest = load("calibration/manifest.json")
        for name, expected in old_manifest["inputs"].items():
            assert sha(root / "calibration/inputs" / name) == expected
    print(
        f"Verified {len(cases)} cases, {results['hook_invocations']} hook invocations, "
        "frozen inputs, source-preservation assertions, and artifact hashes."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    verify(parser.parse_args().results)
