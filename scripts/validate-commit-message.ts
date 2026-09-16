import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";

const HEADER = /^(?:feat|fix|chore|test|refactor|docs)(!)?: \S.*$/u;
const SCISSORS = " ------------------------ >8 ------------------------";
const USAGE = "Usage: pnpm validate:commit <message-file>";

function validate(message: string): string | null {
  const lines = message.split(/\r?\n/u);
  const match = HEADER.exec(lines[0] ?? "");
  if (!match) {
    return "expected 'type[!]: summary' with no scope and a nonempty summary; "
      + "allowed types: feat, fix, chore, test, refactor, docs.";
  }
  if (lines[1]?.trim()) {
    return "separate the header and body with a blank line.";
  }
  if (match[1] && !lines.slice(2).some(line => line.trim())) {
    return "breaking changes (!) require a body explaining the impact and "
      + "migration steps; blank lines and Git comments do not count.";
  }
  return null;
}

function main(args: string[]): number {
  const [messageFile] = args;
  if (args.length === 1 && (messageFile === "-h" || messageFile === "--help")) {
    console.log(USAGE);
    return 0;
  }
  if (args.length !== 1 || messageFile === undefined) {
    console.error(USAGE);
    return 2;
  }

  try {
    let message = readFileSync(messageFile, "utf8");
    const lines = message.split("\n");
    // Verbose editors append a diff below Git's scissors marker. Git removes
    // that suffix after this hook, so it cannot count as an explanation.
    const cut = lines.findIndex((line, index) => index > 0 && line.trimEnd().endsWith(SCISSORS));
    if (cut !== -1) message = lines.slice(0, cut).join("\n");

    // Git passes editor comments to commit-msg before removing them. Use Git's
    // configured comment marker so those comments cannot satisfy the body check.
    const result = spawnSync("git", ["stripspace", "--strip-comments"], {
      input: message,
      encoding: "utf8",
    });
    if (result.error) throw result.error;
    if (result.status !== 0) {
      console.error(`Cannot normalize commit message: ${result.stderr.trim()}`);
      return 1;
    }

    // -m and --cleanup=verbatim can preserve comments and leading blank lines.
    // Validate the literal input too, so normalization cannot hide an invalid header.
    const error = validate(message) || validate(result.stdout);
    if (error) {
      console.error(`Invalid commit message: ${error}`);
      return 1;
    }
    return 0;
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    console.error(`Cannot validate commit message: ${detail}`);
    return 1;
  }
}

process.exitCode = main(process.argv.slice(2));
