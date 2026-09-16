# Consolidated Lefthook documentation

Upstream documentation for **Lefthook v2.1.14**, consolidated into four topic files.

| Reference                                                    | Source pages |
| ------------------------------------------------------------ | ------------ |
| [Getting started and installation](getting-started.md)       | 19           |
| [Configuration reference](configuration.md)                  | 55           |
| [CLI, environment variables, and runtime behavior](usage.md) | 24           |
| [Configuration examples](examples.md)                        | 7            |

## Source and coverage

- Repository: [https://github.com/evilmartians/lefthook](https://github.com/evilmartians/lefthook).
- Commit: [`1e23553eec2392753c5420d348e63a63f517cd45`](https://github.com/evilmartians/lefthook/tree/1e23553eec2392753c5420d348e63a63f517cd45) (v2.1.14).
- Scope: all **106 Markdown pages** under upstream `docs/`, including pages absent from the website navigation.
- **105 pages** are reproduced in the four files. The remaining [`docs/configuration/README.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/README.md) repeats the configuration overview and option index; it is merged into the configuration file's overview and contents.
- Each page section links to its original source at the pinned commit. Tables of contents and internal links navigate within this snapshot.

The consolidation removes website front matter, normalizes headings, renders website callouts as blockquotes, and namespaces anchors and footnotes. Prose is retained with the website's installation-menu reference adapted to a local link. All **178 fenced code examples** are retained; `prettier-ignore` protects them from reformatting. Three upstream links are repaired: `follow`'s link to `parallel`, `commands`' link to its command options, and `remotes`' case-mismatched link to `Scripts.md`.

## Rebuild and verify

From the engineering-standard repository root, with the documented Node/pnpm and Python dependencies installed:

```sh
git clone --depth 1 --branch v2.1.14 https://github.com/evilmartians/lefthook.git /path/to/lefthook
uv run --locked --no-sync python scripts/consolidate-lefthook-docs.py /path/to/lefthook --write
uv run --locked --no-sync python scripts/consolidate-lefthook-docs.py /path/to/lefthook --check
```

The generator requires the exact clean source revision, accounts for every source page, checks code-example preservation and local links, and uses the repository's pinned Prettier. `--check` also compares the generated files with the checked-in snapshot. To update the snapshot, change the revision/version and review the source inventory and link repairs before regenerating.

## Upstream license

Source: [`LICENSE`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/LICENSE).

The MIT License (MIT)

Copyright (c) 2019 Arkweid

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
