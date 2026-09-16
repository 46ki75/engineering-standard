"""Build and verify the pinned Lefthook documentation snapshot."""

import argparse
from collections import Counter
from pathlib import Path
import posixpath
import re
import subprocess
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "skills/engineering-standard/references/lefthook/upstream"
REVISION = "1e23553eec2392753c5420d348e63a63f517cd45"
VERSION = "v2.1.14"
REPOSITORY = "https://github.com/evilmartians/lefthook"


def pages(directory, names):
    return [f"{directory}/{name}.md" for name in names.split()]


BOOKS = {
    "getting-started.md": (
        "Getting started and installation",
        {
            "Overview": ["index.md", "install.md"],
            "Installation methods": pages(
                "installation",
                "ruby node go python swift homebrew winget scoop deb rpm alpine "
                "arch snap devbox mise manual",
            ),
            "Credits": ["misc/contributors.md"],
        },
    ),
    "configuration.md": (
        "Configuration reference",
        {
            "Configuration files": ["configuration.md"],
            "Global options": pages(
                "configuration",
                "min_version lefthook assert_lefthook_installed no_auto_install "
                "install_non_git_hooks ai extends glob_matcher colors output no_tty "
                "rc source_dir source_dir_local skip_lfs templates",
            ),
            "Remote configuration": pages(
                "configuration", "remotes git_url ref refetch refetch_frequency configs"
            ),
            "Hooks and execution flow": pages(
                "configuration",
                "Hook parallel piped follow files-global fail_on_changes "
                "fail_on_changes_diff exclude_tags setup",
            ),
            "Jobs, commands, and scripts": pages(
                "configuration",
                "jobs name run script runner args group Commands Scripts",
            ),
            "File selection and job options": pages(
                "configuration",
                "glob files file_types root exclude skip only tags env fail_text "
                "stage_fixed interactive use_stdin priority",
            ),
        },
    ),
    "usage.md": (
        "CLI, environment variables, and runtime behavior",
        {
            "Basic usage": ["usage.md"],
            "CLI commands": pages(
                "usage/commands",
                "install uninstall run add validate dump check-install self-update version",
            ),
            "Environment variables": pages(
                "usage/envs",
                "LEFTHOOK LEFTHOOK_VERBOSE LEFTHOOK_OUTPUT LEFTHOOK_CONFIG "
                "LEFTHOOK_EXCLUDE LEFTHOOK_BIN CLICOLOR_FORCE NO_COLOR CI",
            ),
            "Runtime features": pages(
                "usage/features", "local git-args git-lfs interactive pass-stdin"
            ),
        },
    ),
    "examples.md": (
        "Configuration examples",
        {
            "Recipes": pages(
                "examples",
                "lefthook-local wrap-commands stage_fixed filters skip remotes commitlint",
            ),
        },
    ),
}

# The legacy index repeats configuration.md; its option list becomes our contents.
ALIASES = {"configuration/README.md": "configuration.md"}
# Repair stale upstream fragments and a case-mismatched filename.
LINK_REPAIRS = {
    ("configuration/follow.md", "#parallel"): "parallel.md",
    ("configuration/Commands.md", "#command"): "#command-options",
    ("configuration/remotes.md", "./scripts.md"): "./Scripts.md",
}
TITLE_OVERRIDES = {
    "configuration/files-global.md": "`files` (hook-level)",
    "configuration/files.md": "`files` (job-level)",
}
FENCE = re.compile(
    r"^(?P<indent>[ >\t]*)(?P<fence>`{3,}|~{3,})(?P<language>[^\n]*)\n"
    r"(?P<body>.*?)^(?P=indent)(?P=fence)[ \t]*$",
    re.MULTILINE | re.DOTALL,
)
HEADING = re.compile(r"^(#{1,6}) (.+)$", re.MULTILINE)
LINK = re.compile(r"(?P<prefix>\]\()(?P<url>[^\s)]+)")
CALLOUT = re.compile(
    r"^::: callout (\w+)(?: ([^\n]+))?\n(.*?)^:::[ \t]*$",
    re.MULTILINE | re.DOTALL,
)


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()


def slug(text):
    return re.sub(r"[^\w\- ]", "", text.lower()).replace(" ", "-")


def anchor(path):
    return "doc-" + slug(path.removesuffix(".md").replace("/", "-"))


def code_blocks(text):
    blocks = []
    for match in FENCE.finditer(text):
        prefix = match["indent"]
        body = "\n".join(
            line.removeprefix(prefix) if line.strip(" >\t") else ""
            for line in match["body"].splitlines()
        )
        blocks.append((match["language"].strip(), body))
    return blocks


def mask_code(text):
    blocks = []

    def replace(match):
        token = f"LEFTHOOK_CODE_{len(blocks)}_END"
        blocks.append((token, match["indent"], match[0]))
        return token

    return FENCE.sub(replace, text), blocks


def load_page(source, path):
    text = (source / "docs" / path).read_text(encoding="utf-8")
    metadata = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    title = None
    if metadata:
        title_match = re.search(r'^title: "(.*)"$', metadata[1], re.MULTILINE)
        title = title_match[1] if title_match else None
        text = text[metadata.end() :]
    text, blocks = mask_code(text.strip())
    first_heading = HEADING.match(text)
    fragments = {}
    if first_heading:
        title = first_heading[2]
        fragments[slug(title)] = anchor(path)
        text = text[first_heading.end() :].lstrip("\n")
    if title is None:
        raise ValueError(f"Missing page title: {path}")
    seen = Counter(fragments.keys())

    def heading(match):
        key = slug(match[2])
        suffix = f"-{seen[key]}" if seen[key] else ""
        seen[key] += 1
        key += suffix
        target = f"{anchor(path)}--{key}"
        fragments[key] = target
        return f'<a id="{target}"></a>\n\n#### {match[2]}'

    text = HEADING.sub(heading, text)
    return TITLE_OVERRIDES.get(path, title), text, blocks, fragments


def rewrite_links(text: str, path: str, locations, documents):
    def replace(match: re.Match[str]) -> str:
        url = LINK_REPAIRS.get((path, match["url"]), match["url"])
        parts = urlsplit(url)
        if parts.scheme or parts.netloc:
            return match[0]
        target = (
            posixpath.normpath(posixpath.join(posixpath.dirname(path), parts.path))
            if parts.path and not parts.path.startswith("/")
            else parts.path.lstrip("/") or path
        )
        target = ALIASES.get(target, target)
        if target not in locations:
            raise ValueError(f"Unresolved documentation link in {path}: {url}")
        fragment = (
            documents[target][3][unquote(parts.fragment)]
            if parts.fragment
            else anchor(target)
        )
        return f"{match['prefix']}{locations[target]}#{fragment}"

    return "\n".join(
        line if line.startswith("[//]:") else LINK.sub(replace, line)
        for line in text.splitlines()
    )


def render_page(path, document, locations, documents):
    title, text, blocks, _ = document
    text = rewrite_links(text, path, locations, documents)
    if path == "install.md":
        text = text.replace(
            "see the options in the dropdown on the left",
            "see [Installation methods](#installation-methods)",
        )
    # Preserve the contributor-list generation command without Markdown escaping.
    text = re.sub(r"^\[//\]: # '(.*)'$", r"<!-- \1 -->", text, flags=re.MULTILINE)
    text = re.sub(r"\[\^([^\]]+)\]", rf"[^{anchor(path)}-\1]", text)
    for token, indent, block in blocks:
        text = text.replace(token, f"\n{indent}<!-- prettier-ignore -->\n\n{block}\n")

    def callout(match):
        title = match[2] or {"warn": "Warning", "info": "Note"}.get(
            match[1], match[1].capitalize()
        )
        body = "\n".join("> " + line if line else ">" for line in match[3].splitlines())
        return f"> **{title}**\n>\n{body}\n"

    text = CALLOUT.sub(callout, text)
    if ":::" in mask_code(text)[0]:
        raise ValueError(f"Unsupported callout in {path}")
    return (
        f'<a id="{anchor(path)}"></a>\n\n### {title}\n\n'
        f"Source: [`docs/{path}`]({REPOSITORY}/blob/{REVISION}/docs/{path}).\n\n"
        f"{text.strip()}\n"
    )


def format_markdown(text):
    return subprocess.run(
        ["pnpm", "exec", "prettier", "--parser", "markdown"],
        input=text,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
        cwd=ROOT,
    ).stdout


def verify_links(outputs):
    ids = {}
    for filename, text in outputs.items():
        masked, _ = mask_code(text)
        explicit = re.findall(r'<a id="([^"]+)"></a>', masked)
        if len(explicit) != len(set(explicit)):
            raise ValueError(f"Duplicate anchors in {filename}")
        ids[filename] = set(explicit) | {slug(m[2]) for m in HEADING.finditer(masked)}
    count = 0
    for filename, text in outputs.items():
        masked, _ = mask_code(text)
        masked = re.sub(r"<!--.*?-->", "", masked, flags=re.DOTALL)
        for line in masked.splitlines():
            if line.startswith("[//]:"):
                continue
            for match in LINK.finditer(line):
                parts = urlsplit(match["url"])
                if parts.scheme or parts.netloc:
                    continue
                target = parts.path or filename
                if target not in ids or (
                    parts.fragment and unquote(parts.fragment) not in ids[target]
                ):
                    raise ValueError(f"Broken link in {filename}: {match['url']}")
                count += 1
    return count


def build(source):
    if git(source, "rev-parse", "HEAD") != REVISION:
        raise ValueError(f"Expected upstream commit {REVISION}")
    if git(source, "status", "--porcelain", "--", "docs", "LICENSE"):
        raise ValueError("Upstream documentation or license has local changes")
    selected = [
        p for _, groups in BOOKS.values() for paths in groups.values() for p in paths
    ]
    found = {
        p.relative_to(source / "docs").as_posix()
        for p in (source / "docs").rglob("*.md")
    }
    if len(selected) != len(set(selected)) or set(selected) | set(ALIASES) != found:
        raise ValueError(
            f"Source coverage mismatch: {found ^ (set(selected) | set(ALIASES))}"
        )
    documents = {path: load_page(source, path) for path in selected}
    locations = {
        p: book
        for book, (_, groups) in BOOKS.items()
        for paths in groups.values()
        for p in paths
    }
    outputs = {}
    total_blocks = 0
    for filename, (title, groups) in BOOKS.items():
        paths = [p for group in groups.values() for p in group]
        contents = [
            f"# {title}\n\n[Snapshot index](README.md) · Lefthook {VERSION}.\n\n## Contents\n"
        ]
        for group, members in groups.items():
            contents.append(f"- [{group}](#{slug(group)})")
            contents.extend(f"  - [{documents[p][0]}](#{anchor(p)})" for p in members)
        for group, members in groups.items():
            contents.append(f"\n## {group}\n")
            contents.extend(
                render_page(p, documents[p], locations, documents) for p in members
            )
        output = format_markdown("\n".join(contents))
        expected = [
            b
            for p in paths
            for b in code_blocks((source / "docs" / p).read_text(encoding="utf-8"))
        ]
        if code_blocks(output) != expected:
            raise ValueError(f"Code examples changed in {filename}")
        total_blocks += len(expected)
        outputs[filename] = output
    table = "\n".join(
        f"| [{title}]({name}) | {sum(map(len, groups.values()))} |"
        for name, (title, groups) in BOOKS.items()
    )
    outputs["README.md"] = format_markdown(
        f"""# Consolidated Lefthook documentation

Upstream documentation for **Lefthook {VERSION}**, consolidated into four topic files.

| Reference | Source pages |
| --- | --- |
{table}

## Source and coverage

- Repository: [{REPOSITORY}]({REPOSITORY}).
- Commit: [`{REVISION}`]({REPOSITORY}/tree/{REVISION}) ({VERSION}).
- Scope: all **{len(found)} Markdown pages** under upstream `docs/`, including pages absent from the website navigation.
- **{len(selected)} pages** are reproduced in the four files. The remaining [`docs/configuration/README.md`]({REPOSITORY}/blob/{REVISION}/docs/configuration/README.md) repeats the configuration overview and option index; it is merged into the configuration file's overview and contents.
- Each page section links to its original source at the pinned commit. Tables of contents and internal links navigate within this snapshot.

The consolidation removes website front matter, normalizes headings, renders website callouts as blockquotes, and namespaces anchors and footnotes. Prose is retained with the website's installation-menu reference adapted to a local link. All **{total_blocks} fenced code examples** are retained; `prettier-ignore` protects them from reformatting. Three upstream links are repaired: `follow`'s link to `parallel`, `commands`' link to its command options, and `remotes`' case-mismatched link to `Scripts.md`.

## Rebuild and verify

From the engineering-standard repository root, with the documented Node/pnpm and Python dependencies installed:

```sh
git clone --depth 1 --branch {VERSION} https://github.com/evilmartians/lefthook.git /path/to/lefthook
uv run --locked --no-sync python scripts/consolidate-lefthook-docs.py /path/to/lefthook --write
uv run --locked --no-sync python scripts/consolidate-lefthook-docs.py /path/to/lefthook --check
```

The generator requires the exact clean source revision, accounts for every source page, checks code-example preservation and local links, and uses the repository's pinned Prettier. `--check` also compares the generated files with the checked-in snapshot. To update the snapshot, change the revision/version and review the source inventory and link repairs before regenerating.

## Upstream license

Source: [`LICENSE`]({REPOSITORY}/blob/{REVISION}/LICENSE).

{(source / "LICENSE").read_text(encoding="utf-8").strip()}
"""
    )
    links = verify_links(outputs)
    print(
        f"Verified {len(found)} source pages, {total_blocks} code examples, and {links} local links."
    )
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", type=Path, help="Clean Lefthook checkout at the pinned revision"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = build(args.source.resolve())
    if args.write:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for filename, text in outputs.items():
            (OUTPUT / filename).write_text(text, encoding="utf-8", newline="\n")
        print(f"Wrote {len(outputs)} Markdown files to {OUTPUT.relative_to(ROOT)}")
    else:
        for filename, text in outputs.items():
            if (
                not (OUTPUT / filename).exists()
                or (OUTPUT / filename).read_text(encoding="utf-8") != text
            ):
                raise SystemExit(f"Snapshot differs: {OUTPUT / filename}")
        print("Snapshot matches the pinned source.")


if __name__ == "__main__":
    main()
