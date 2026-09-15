#!/usr/bin/env python3
"""Start a separate judging study with copied writers and fresh paired controls.

init runs metadata-only preflight; controls makes exactly 12 fresh judge calls.
Continue with full.py judges/status/summarize using the new output directory.
"""

from contextlib import contextmanager
import argparse
import fcntl
from pathlib import Path
import re
import shutil
import sys


sys.dont_write_bytecode = True
if __package__:
    from . import controls, full
else:
    import controls
    import full


@contextmanager
def override(module, name, value):
    original = getattr(module, name)
    setattr(module, name, value)
    try:
        yield
    finally:
        setattr(module, name, original)


def validate_model(model):
    if not isinstance(model, str) or not re.fullmatch(
        r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+", model
    ):
        raise ValueError("Judge model must be providerID/modelID")
    if model == full.base.WRITER_MODEL:
        raise ValueError("Judge must differ from the writer model")


def recovery_source():
    script = Path(__file__).resolve()
    return {
        "script": str(script.relative_to(full.ROOT)),
        "script_sha256": full.file_hash(script),
        "new_writer_calls": 0,
        "interpretation": "Separate judging study; original coverage is not repaired.",
    }


def writer_hashes(output):
    root = output / "writers"
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Expected a local writer artifact subtree")
    hashes = {}
    for path in sorted(root.rglob("*")):
        # Copies must never follow links into unrelated source or credential files.
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("Unsupported writer artifact path")
        if path.is_file():
            hashes[str(path.relative_to(output))] = full.file_hash(path)
    return hashes


def verified_writers(source, frozen):
    entries = {}
    cases = {case["id"]: case for case in frozen["inputs"]["cases"]}
    for job in frozen["jobs"]["writers"]:
        entry = full.inspect_job(
            source, "writers", job, frozen["max_attempts"], verify=True
        )
        selected = entry["selected_first_valid"]
        if selected is None or any(
            attempt["status"] == "incomplete" for attempt in entry["attempts"]
        ):
            raise ValueError(
                "All writers must be selected-valid with finalized attempts"
            )
        attempt = entry["attempts"][selected - 1]
        hashes = attempt["artifact_sha256"]
        expected = {
            "system.md": full.base.digest(frozen["inputs"]["systems"][job["arm"]]),
            "input.md": full.base.digest(full.base.writer_prompt(cases[job["case"]])),
        }
        if any(hashes.get(name) != digest for name, digest in expected.items()):
            raise ValueError("Selected writer inputs differ from the frozen study")
        if not {"output.md", "result.json"} <= hashes.keys():
            raise ValueError("Selected writer lacks required artifacts")
        entries[job["id"]] = entry
    return entries


def initialize(source, output, judge_model):
    validate_model(judge_model)
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Source and output directories must not overlap")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("A new judging study requires an empty output directory")
    # Open the existing lock read-only: validation must not mutate the old study.
    with (source / ".execution.lock").open("rb") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            raise full.OutputBusy(
                "Another command is using the source directory"
            ) from None
        original = full.load_frozen(source)
        full.require_ready(source, original)
        if judge_model in (original["writer_model"], original["judge_model"]):
            raise ValueError("Recovery requires a different judge model")
        hashes = writer_hashes(source)
        entries = verified_writers(source, original)
        provenance = {
            **recovery_source(),
            "source_output": str(source),
            "source_manifest_sha256": original["manifest_sha256"],
            "source_manifest_file_sha256": full.file_hash(source / "manifest.json"),
            "source_judge_model": original["judge_model"],
            "writer_reuse": "byte-for-byte copies of all attempts; historical usage",
            "writer_jobs": len(entries),
            "writer_attempts": sum(len(e["attempts"]) for e in entries.values()),
            "selected_writer_attempts": {
                ident: entry["selected_first_valid"] for ident, entry in entries.items()
            },
            "writer_artifact_sha256": hashes,
            "reused_judge_attempts": 0,
            "fresh_judge_jobs": len(original["jobs"]["judges"]),
            "fresh_judge_splits": list(full.SPLITS),
        }
        make_manifest = full.make_manifest

        def make_recovery_manifest(*args, **kwargs):
            frozen = make_manifest(*args, **kwargs)
            for field in (
                "inputs",
                "jobs",
                "policy",
                "analysis_plan",
                "writer_model",
                "writer_variant",
                "output_token_limit_requested",
                "opencode_version_required",
            ):
                if frozen[field] != original[field]:
                    raise ValueError(
                        "Recovery would change a frozen study setting: " + field
                    )
            frozen["recovery"] = provenance
            frozen.pop("manifest_sha256")
            frozen["manifest_sha256"] = full.json_hash(frozen)
            # initialize holds the destination lock and has checked emptiness.
            # Install and verify every copy BEFORE it publishes manifest/ready.
            shutil.copytree(source / "writers", output / "writers", symlinks=True)
            if writer_hashes(output) != hashes:
                raise ValueError("Copied writer artifacts differ from the source")
            verified_writers(output, frozen)
            return frozen

        with (
            override(full.base, "JUDGE_MODEL", judge_model),
            override(full, "make_manifest", make_recovery_manifest),
        ):
            frozen = full.initialize(
                output, original["seed"], original["timeout"], original["max_attempts"]
            )
    return {
        **full.status(output, frozen),
        "judge_model": frozen["judge_model"],
        "judge_variant": frozen["judge_variant"],
        "source_manifest_sha256": original["manifest_sha256"],
        "new_writer_calls": 0,
    }


def run_controls(output, judge_model, concurrency=3):
    validate_model(judge_model)
    if type(concurrency) is not int or concurrency < 1:
        raise ValueError("Concurrency must be positive")
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Controls require a new output directory")
    # trial passes manifest model/variant explicitly, bypassing the adapter's
    # import-time default. Restore the constant before starting any worker.
    with override(controls.run, "JUDGE_MODEL", judge_model):
        manifest = controls.build_manifest()
    if len(manifest["controls"]) != 6 or len(manifest["jobs"]) != 12:
        raise ValueError("Expected six paired controls and twelve fresh trials")
    manifest["recovery"] = recovery_source()
    controls.execute(output, manifest, concurrency)
    report = controls.summarize(manifest, controls.collect(output, manifest))
    controls.save(output / "summary.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Reuse writers; metadata-only preflight")
    init.add_argument("--source", type=Path, required=True)
    control = commands.add_parser("controls", help="Run twelve fresh paired controls")
    control.add_argument("--concurrency", type=int, default=3)
    for command in (init, control):
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--judge-model", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            report = initialize(args.source, args.output, args.judge_model)
            exit_code = 0
        else:
            report = run_controls(args.output, args.judge_model, args.concurrency)
            exit_code = int(report["counts"]["valid"] != 12)
        print(full.json_text(report), end="")
        return exit_code
    except KeyboardInterrupt:
        print("Interrupted; retained artifacts are unchanged.", file=sys.stderr)
        return 130
    except (ValueError, OSError, KeyError, TypeError) as error:
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        print("Error: " + message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
