import assert from "node:assert/strict";
import { spawnSync, type SpawnSyncReturns } from "node:child_process";
import {
  accessSync,
  constants,
  copyFileSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test, type TestContext } from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("../", import.meta.url));
const withoutTrailingNewlines = (text: string): string =>
  text.replace(/\n+$/u, "");
const shellQuote = (value: string): string =>
  `'${value.replaceAll("'", "'\\''")}'`;

interface RunOptions {
  cwd?: string;
  check?: boolean;
}

interface CommitOptions {
  accepted: boolean;
  options?: string[];
}

class Fixture {
  readonly directory: string;
  readonly repo: string;
  readonly env: NodeJS.ProcessEnv;
  private sequence = 0;

  constructor(t: TestContext) {
    this.directory = mkdtempSync(join(tmpdir(), "commit-hooks-"));
    t.after(() => rmSync(this.directory, { recursive: true, force: true }));
    this.repo = join(this.directory, "repository with spaces");
    this.env = Object.fromEntries(
      Object.entries(process.env).filter(
        ([key]) =>
          !key.startsWith("GIT_") &&
          !key.startsWith("LEFTHOOK") &&
          key !== "CI",
      ),
    );
    Object.assign(this.env, {
      GIT_CONFIG_NOSYSTEM: "1",
      GIT_CONFIG_GLOBAL: process.platform === "win32" ? "NUL" : "/dev/null",
      GIT_TERMINAL_PROMPT: "0",
      NO_COLOR: "1",
    });
    this.git(["clone", "--quiet", "--no-hardlinks", ROOT, this.repo], {
      cwd: this.directory,
    });
    mkdirSync(join(this.repo, "scripts"), { recursive: true });
    for (const relative of [
      ".gitignore",
      "package.json",
      "pnpm-lock.yaml",
      "pnpm-workspace.yaml",
      "tsconfig.json",
      "lefthook.yml",
      "scripts/validate-commit-message.ts",
    ]) {
      copyFileSync(join(ROOT, relative), join(this.repo, relative));
    }
    // Reuse the installed, pinned tools so each disposable copy can test hooks offline.
    symlinkSync(
      join(ROOT, "node_modules"),
      join(this.repo, "node_modules"),
      "junction",
    );
  }

  run(
    command: string,
    args: readonly string[],
    { cwd = this.repo, check = true }: RunOptions = {},
  ): SpawnSyncReturns<string> {
    const result = spawnSync(command, args, {
      cwd,
      env: this.env,
      encoding: "utf8",
      timeout: 30_000,
    });
    if (result.error) throw result.error;
    if (check) assert.equal(result.status, 0, result.stdout + result.stderr);
    return result;
  }

  git(
    args: readonly string[],
    options: RunOptions = {},
  ): SpawnSyncReturns<string> {
    return this.run(
      "git",
      [
        "-c",
        "user.name=Hook Test",
        "-c",
        "user.email=hook-test@example.invalid",
        "-c",
        "commit.gpgSign=false",
        ...args,
      ],
      options,
    );
  }

  installHook(): void {
    this.run("pnpm", ["hooks:install"]);
    accessSync(join(this.repo, ".git/hooks/commit-msg"), constants.X_OK);
  }

  stageChange(): void {
    this.sequence += 1;
    writeFileSync(
      join(this.repo, "hook-test-fixture.txt"),
      `Change ${this.sequence}\n`,
    );
    this.git(["add", "--", "hook-test-fixture.txt"]);
  }

  assertCommit(
    message: string,
    { accepted, options = [] }: CommitOptions,
  ): void {
    this.stageChange();
    const before = this.git(["rev-parse", "HEAD"]).stdout;
    const staged = this.git(["diff", "--cached", "--binary"]).stdout;
    const result = this.git(["commit", ...options, "-m", message], {
      check: false,
    });
    const after = this.git(["rev-parse", "HEAD"]).stdout;
    const output = result.stdout + result.stderr;
    if (accepted) {
      assert.equal(result.status, 0, output);
      assert.notEqual(before, after);
      assert.equal(
        withoutTrailingNewlines(this.git(["log", "-1", "--format=%B"]).stdout),
        withoutTrailingNewlines(message),
      );
      assert.equal(this.git(["diff", "--cached"]).stdout, "");
    } else {
      assert.notEqual(result.status, 0, output);
      assert.match(output, /Invalid commit message:/u);
      assert.equal(before, after);
      assert.equal(this.git(["diff", "--cached", "--binary"]).stdout, staged);
    }
  }

  setEditor(message: string): void {
    const editor = join(this.directory, "message editor.mjs");
    writeFileSync(
      editor,
      'import { readFileSync, writeFileSync } from "node:fs";\n' +
        "const path = process.argv[2];\n" +
        `writeFileSync(path, ${JSON.stringify(message)} + readFileSync(path, "utf8"));\n`,
    );
    this.env.GIT_EDITOR = [process.execPath, editor].map(shellQuote).join(" ");
  }
}

test("the same invalid message is accepted before installation and rejected afterward", (t) => {
  const fixture = new Fixture(t);
  fixture.assertCommit("update dependencies", { accepted: true });
  fixture.installHook();
  fixture.assertCommit("update dependencies", { accepted: false });
});

test("allowed types work with and without a breaking-change marker", (t) => {
  const fixture = new Fixture(t);
  fixture.installHook();
  for (const kind of ["feat", "fix", "chore", "test", "refactor", "docs"]) {
    for (const breaking of [false, true]) {
      let message = `${kind}${breaking ? "!" : ""}: update café example`;
      if (breaking) {
        message +=
          "\n\nThe old example API is removed. " +
          "Replace old_example() with new_example().";
      }
      fixture.assertCommit(message, { accepted: true });
    }
  }
});

test("invalid headers are rejected", (t) => {
  const fixture = new Fixture(t);
  fixture.installHook();
  for (const message of [
    "",
    "update dependencies",
    "Fix: correct redirect",
    "build: update dependencies",
    "fix(auth): correct redirect",
    "fix:",
    "fix: ",
    "fix: \t",
    "fix:\tcorrect redirect",
    "feat!!: remove old API",
    "feat !: remove old API",
    "# literal comment\nfix: correct redirect",
  ]) {
    fixture.assertCommit(message, { accepted: false });
  }
});

test("breaking changes need a non-comment body", (t) => {
  const fixture = new Fixture(t);
  fixture.installHook();
  for (const body of ["", "\n\n", "\n\n \t\n", "\n\n# editor guidance\n"]) {
    fixture.assertCommit(`feat!: remove old API${body}`, { accepted: false });
  }
});

test("bodies need a blank separator", (t) => {
  const fixture = new Fixture(t);
  fixture.installHook();
  fixture.assertCommit("fix: correct redirect\nExplain the change.", {
    accepted: false,
  });
  fixture.assertCommit("feat!: remove old API\nUse new_api().", {
    accepted: false,
  });
});

test("editor comments and verbose diffs do not satisfy the body requirement", (t) => {
  const fixture = new Fixture(t);
  fixture.installHook();
  fixture.setEditor("feat!: remove old API\n");
  for (const marker of ["#", ";"]) {
    for (const options of [[], ["--verbose"]]) {
      fixture.stageChange();
      const before = fixture.git(["rev-parse", "HEAD"]).stdout;
      const staged = fixture.git(["diff", "--cached", "--binary"]).stdout;
      const result = fixture.git(
        ["-c", `core.commentChar=${marker}`, "commit", ...options],
        { check: false },
      );
      assert.notEqual(result.status, 0, result.stdout + result.stderr);
      assert.match(result.stdout + result.stderr, /Invalid commit message:/u);
      assert.equal(fixture.git(["rev-parse", "HEAD"]).stdout, before);
      assert.equal(
        fixture.git(["diff", "--cached", "--binary"]).stdout,
        staged,
      );
    }
  }
});

test("verbatim cleanup cannot bypass header validation", (t) => {
  const fixture = new Fixture(t);
  fixture.installHook();
  fixture.assertCommit("\nfix: correct redirect", {
    accepted: false,
    options: ["--cleanup=verbatim"],
  });
});

test("an editor accepts a breaking-change body alongside a verbose diff", (t) => {
  const fixture = new Fixture(t);
  fixture.installHook();
  const message =
    "feat!: remove old API\n\n" +
    "The old API is removed. Replace old_api() with new_api().\n";
  fixture.setEditor(message);
  fixture.stageChange();
  fixture.git(["commit", "--verbose"]);
  assert.equal(
    withoutTrailingNewlines(fixture.git(["log", "-1", "--format=%B"]).stdout),
    withoutTrailingNewlines(message),
  );
  assert.equal(fixture.git(["diff", "--cached"]).stdout, "");
});

test("amend accepts valid messages and rejects invalid messages", (t) => {
  const fixture = new Fixture(t);
  fixture.installHook();
  fixture.assertCommit("fix: initial correction", { accepted: true });
  fixture.assertCommit("fix: improved correction", {
    accepted: true,
    options: ["--amend"],
  });
  fixture.assertCommit("invalid amendment", {
    accepted: false,
    options: ["--amend"],
  });
});

test("message paths with spaces work and message files are not edited", (t) => {
  const fixture = new Fixture(t);
  fixture.installHook();
  const path = join(fixture.directory, "commit message.txt");
  for (const [message, accepted] of [
    ["docs: explain setup\n\n# Preserve this literal heading.\n", true],
    ["invalid message\n", false],
  ] as const) {
    const original = Buffer.from(message);
    writeFileSync(path, original);
    const result = fixture.git(["hook", "run", "commit-msg", "--", path], {
      check: false,
    });
    assert.equal(result.status === 0, accepted, result.stdout + result.stderr);
    assert.deepEqual(readFileSync(path), original);
  }
});

test("a missing message file fails validation", (t) => {
  const fixture = new Fixture(t);
  fixture.installHook();
  const result = fixture.git(
    ["hook", "run", "commit-msg", "--", "missing-message.txt"],
    { check: false },
  );
  assert.notEqual(result.status, 0);
  assert.match(
    result.stdout + result.stderr,
    /Cannot validate commit message:/u,
  );
});

test("--no-verify bypasses the hook", (t) => {
  const fixture = new Fixture(t);
  fixture.installHook();
  fixture.assertCommit("invalid message", {
    accepted: true,
    options: ["--no-verify"],
  });
});
