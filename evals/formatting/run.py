#!/usr/bin/env python3
"""Run real formatter comparisons in an explicitly initialized temporary tree."""

from __future__ import annotations

import argparse
import tarfile
import zipfile
from pathlib import Path

from harness import COMMIT, PLUGIN, Harness, download, initialize, save


def setup(args):
    h = initialize(args.root, args.source)
    for repo in (h.baseline, h.candidate):
        h.require(
            ["git", "clone", "--no-local", "--no-checkout", h.manifest["source"], repo],
            cwd=h.root,
        )
        h.require(["git", "checkout", "--detach", COMMIT], cwd=repo)
    downloads = h.manifest["downloads"]
    for url, name in [
        ("https://registry.npmjs.org/pnpm/-/pnpm-9.12.3.tgz", "pnpm.tgz"),
        (PLUGIN, "exec-0.7.3.json"),
        (
            "https://releases.hashicorp.com/terraform/1.16.2/terraform_1.16.2_darwin_arm64.zip",
            "terraform.zip",
        ),
        (
            "https://releases.hashicorp.com/terraform/1.16.2/terraform_1.16.2_SHA256SUMS",
            "terraform-SHA256SUMS",
        ),
    ]:
        path = h.tools / name
        downloads[url] = download(url, path)
    # All archives are pinned official distributions; reject traversal members.
    with tarfile.open(h.tools / "pnpm.tgz") as archive:
        for member in archive.getmembers():
            target = (h.tools / "pnpm" / member.name).resolve()
            if (
                not target.is_relative_to(h.tools / "pnpm")
                or member.issym()
                or member.islnk()
            ):
                raise ValueError(f"Unsafe archive member: {member.name}")
        archive.extractall(h.tools / "pnpm")
    (h.tools / "bin/pnpm").symlink_to(h.tools / "pnpm/package/bin/pnpm.cjs")
    expected = next(
        line.split()[0]
        for line in (h.tools / "terraform-SHA256SUMS").read_text().splitlines()
        if line.endswith("terraform_1.16.2_darwin_arm64.zip")
    )
    terraform_url = "https://releases.hashicorp.com/terraform/1.16.2/terraform_1.16.2_darwin_arm64.zip"
    assert downloads[terraform_url] == expected
    with zipfile.ZipFile(h.tools / "terraform.zip") as archive:
        (h.tools / "bin/terraform").write_bytes(archive.read("terraform"))
    (h.tools / "bin/terraform").chmod(0o755)
    h.manifest["plugin"] = PLUGIN + "@" + downloads[PLUGIN]
    save(h.root / "evaluation.json", h.manifest)
    h.require(
        [
            "rustup",
            "toolchain",
            "install",
            "1.93.0",
            "--profile",
            "minimal",
            "--component",
            "rustfmt",
            "--component",
            "clippy",
        ],
        timeout=600,
    )
    h.require(["uv", "tool", "install", "ruff==0.15.19"], timeout=180)
    for repo in (h.baseline, h.candidate):
        h.require(
            [
                "pnpm",
                "install",
                "--frozen-lockfile",
                "--ignore-scripts",
                "--store-dir",
                h.root / "environments/pnpm-store",
            ],
            cwd=repo,
            timeout=600,
            label="pnpm-install",
        )
    versions = {}
    for tool in ("dprint", "node", "pnpm", "rustfmt", "cargo", "ruff", "terraform"):
        versions[tool] = h.require([tool, "--version"]).decode().strip()
    versions["prettier"] = (
        h.require(
            ["pnpm", "exec", "prettier", "--version"],
            cwd=h.candidate / "packages/web-solid",
        )
        .decode()
        .strip()
    )
    h.manifest["versions"] = versions
    h.manifest["snapshot_hashes"] = h.snapshot(h.baseline)
    save(h.root / "evaluation.json", h.manifest)
    h.record_phase("setup", {"versions": versions, "downloads": downloads})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase",
        choices=[
            "setup",
            "pilot",
            "corpus",
            "behavior",
            "timing",
            "compatibility",
            "rust-compatibility",
            "editors",
            "vscode",
            "representative",
            "extensions",
            "example",
            "editor-actions",
            "hooks",
            "export",
        ],
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.phase == "setup":
        if args.source is None:
            parser.error("setup requires --source")
        setup(args)
    else:
        from experiments import run_phase

        run_phase(Harness(args.root), args)


if __name__ == "__main__":
    main()
