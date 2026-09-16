# CLI, environment variables, and runtime behavior

[Snapshot index](README.md) · Lefthook v2.1.14.

## Contents

- [Basic usage](#basic-usage)
  - [Usage](#doc-usage)
- [CLI commands](#cli-commands)
  - [`lefthook install`](#doc-usage-commands-install)
  - [`lefthook uninstall`](#doc-usage-commands-uninstall)
  - [`lefthook run`](#doc-usage-commands-run)
  - [`lefthook add`](#doc-usage-commands-add)
  - [`lefthook validate`](#doc-usage-commands-validate)
  - [`lefthook dump`](#doc-usage-commands-dump)
  - [`lefthook check-install`](#doc-usage-commands-check-install)
  - [`lefthook self-update`](#doc-usage-commands-self-update)
  - [`lefthook version`](#doc-usage-commands-version)
- [Environment variables](#environment-variables)
  - [`LEFTHOOK`](#doc-usage-envs-lefthook)
  - [`LEFTHOOK_VERBOSE`](#doc-usage-envs-lefthook_verbose)
  - [`LEFTHOOK_OUTPUT`](#doc-usage-envs-lefthook_output)
  - [`LEFTHOOK_CONFIG`](#doc-usage-envs-lefthook_config)
  - [`LEFTHOOK_EXCLUDE`](#doc-usage-envs-lefthook_exclude)
  - [`LEFTHOOK_BIN`](#doc-usage-envs-lefthook_bin)
  - [`CLICOLOR_FORCE`](#doc-usage-envs-clicolor_force)
  - [`NO_COLOR`](#doc-usage-envs-no_color)
  - [`CI`](#doc-usage-envs-ci)
- [Runtime features](#runtime-features)
  - [Local config](#doc-usage-features-local)
  - [Capture ARGS from git in the script](#doc-usage-features-git-args)
  - [Git LFS support](#doc-usage-features-git-lfs)
  - [Using an interactive command or script](#doc-usage-features-interactive)
  - [Pass stdin to a command or script](#doc-usage-features-pass-stdin)

## Basic usage

<a id="doc-usage"></a>

### Usage

Source: [`docs/usage.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage.md).

Here are the most common usage cases. You can find more info in the docs.

<a id="doc-usage--basic-cli-commands"></a>

#### Basic CLI commands

<!-- prettier-ignore -->
```bash
# Create/update Git hooks based on lefthook.yml, or create an empty lefthook.yml
lefthook install

# Run pre-commit hook commands and scripts (requires lefthook.yml)
lefthook run pre-commit

# Validate the configuration
lefthook validate

# Dump the configuration (useful when you have remotes, extends that overwrite the configuration)
lefthook dump
```

<a id="doc-usage--skip-running-lefthook-when-committing-changes"></a>

#### Skip running lefthook when committing changes

<!-- prettier-ignore -->
```bash
LEFTHOOK=0 git commit
```

## CLI commands

<a id="doc-usage-commands-install"></a>

### `lefthook install`

Source: [`docs/usage/commands/install.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/commands/install.md).

Creates an empty `lefthook.yml` if a configuration file does not exist.

Installs configured hooks to Git hooks.

> **Note**
>
> Reinstall is not required when you modify `lefthook.yml`, the configuration file is read every time a git hook is run.

> **Note**
>
> NPM package `lefthook` installs the hooks in a postinstall script automatically. For projects not using NPM package run `lefthook install` after cloning the repo.
>
> The postinstall script runs a plain `lefthook install`, so when `core.hooksPath` is set it stops and prints the same message as running the command by hand. Run `lefthook install --force` or `lefthook install --reset-hooks-path` once, deliberately, to resolve it.

<a id="doc-usage-commands-install--installing-specific-hooks"></a>

#### Installing specific hooks

You can install only specific hooks by running `lefthook install <hook-1> <hook-2> ...`.

<a id="doc-usage-commands-uninstall"></a>

### `lefthook uninstall`

Source: [`docs/usage/commands/uninstall.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/commands/uninstall.md).

Clears Git hooks installed by lefthook.

<a id="doc-usage-commands-run"></a>

### `lefthook run`

Source: [`docs/usage/commands/run.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/commands/run.md).

Executes the commands and scripts configured for a given hook. Installed Git hooks call `lefthook run` implicitly.

<a id="doc-usage-commands-run--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  jobs:
    - name: lint
      run: yarn lint --fix {staged_files}

test:
  jobs:
    - name: test
      run: yarn test
```

Install the hook.

<!-- prettier-ignore -->
```bash
$ lefthook install
```

<!-- prettier-ignore -->
```bash
$ lefthook run test # will run 'yarn test'
$ git commit # will run pre-commit hook ('yarn lint --fix')
$ lefthook run pre-commit # will run pre-commit hook (`yarn lint --fix`)
```

<a id="doc-usage-commands-run--run-specific-jobs"></a>

#### Run specific jobs

You can specify which jobs to run (also `--tag` supported).

<!-- prettier-ignore -->
```bash
$ lefthook run pre-commit --job lints --job pretty --tag checks
```

<a id="doc-usage-commands-run--specify-files"></a>

#### Specify files

You can force replacing files templates (like `{staged_files}`) with either all files (will acts as `{all_files}` template) or a list of files.

<!-- prettier-ignore -->
```bash
$ lefthook run pre-commit --all-files
$ lefthook run pre-commit --file file1.js --file file2.js
```

(if both are specified, `--all-files` is ignored)

<a id="doc-usage-commands-add"></a>

### `lefthook add`

Source: [`docs/usage/commands/add.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/commands/add.md).

Installs the given hook to Git hook.

With argument `--dirs` creates a directory `.git/hooks/<hook name>/` if it doesn't exist. Use it before adding a script to configuration.

<a id="doc-usage-commands-add--example"></a>

#### Example

<!-- prettier-ignore -->
```bash
$ lefthook add pre-push  --dirs
```

Describe pre-push commands in `lefthook.yml`:

<!-- prettier-ignore -->
```yml
pre-push:
  jobs:
    - script: "audit.sh"
      runner: bash
```

Edit the script:

<!-- prettier-ignore -->
```bash
$ vim .lefthook/pre-push/audit.sh
...
```

Run `git push` and lefthook will run `bash audit.sh` as a pre-push hook.

<a id="doc-usage-commands-validate"></a>

### `lefthook validate`

Source: [`docs/usage/commands/validate.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/commands/validate.md).

Validates your lefthook configuration. Use `lefthook dump` to see it.

It uses JSON schema from the lefthook Github repo.

<a id="doc-usage-commands-dump"></a>

### `lefthook dump`

Source: [`docs/usage/commands/dump.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/commands/dump.md).

Prints the whole configuration after merging all secondary configs.

This is the actual config lefthook uses, it can be build from the main config (`lefthook.yml`), remotes, extends, and `lefthook-local.yml` overrides.

<a id="doc-usage-commands-check-install"></a>

### `lefthook check-install`

Source: [`docs/usage/commands/check-install.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/commands/check-install.md).

Checks if Git hooks are installed and synchronized.

Returns:

- `0` if hooks installed and synchronized
- `1` if hooks not installed or need a sync

<a id="doc-usage-commands-self-update"></a>

### `lefthook self-update`

Source: [`docs/usage/commands/self-update.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/commands/self-update.md).

Updates the binary with the latest lefthook release on Github.

This command is available only if you install lefthook from sources or download the binary from the Github Releases. For other ways use package-specific commands to update lefthook.

<a id="doc-usage-commands-version"></a>

### `lefthook version`

Source: [`docs/usage/commands/version.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/commands/version.md).

`lefthook version` prints the current binary version. Print the commit hash with `lefthook version --full`

<a id="doc-usage-commands-version--example"></a>

#### Example

<!-- prettier-ignore -->
```bash
$ lefthook version --full

1.1.3 bb099d13c24114d2859815d9d23671a32932ffe2
```

## Environment variables

<a id="doc-usage-envs-lefthook"></a>

### `LEFTHOOK`

Source: [`docs/usage/envs/LEFTHOOK.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/envs/LEFTHOOK.md).

Use `LEFTHOOK=0 git ...` or `LEFTHOOK=false git ...` to disable lefthook when running git commands.

<a id="doc-usage-envs-lefthook--example"></a>

#### Example

<!-- prettier-ignore -->
```bash
LEFTHOOK=0 git commit -am "Lefthook skipped"
```

When using NPM package `lefthook` in CI, and your CI sets `CI=true` automatically, use `LEFTHOOK=1` or `LEFTHOOK=true` to install hooks in the postinstall script:

<a id="doc-usage-envs-lefthook--example-1"></a>

#### Example

<!-- prettier-ignore -->
```bash
LEFTHOOK=1 npm install
LEFTHOOK=1 yarn install
LEFTHOOK=1 pnpm install
```

<a id="doc-usage-envs-lefthook_verbose"></a>

### `LEFTHOOK_VERBOSE`

Source: [`docs/usage/envs/LEFTHOOK_VERBOSE.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/envs/LEFTHOOK_VERBOSE.md).

Set `LEFTHOOK_VERBOSE=1` or `LEFTHOOK_VERBOSE=true` to enable verbose printing.

<a id="doc-usage-envs-lefthook_verbose--example"></a>

#### Example

<!-- prettier-ignore -->
```bash
LEFTHOOK_VERBOSE=1 lefthook run pre-commit
```

<a id="doc-usage-envs-lefthook_output"></a>

### `LEFTHOOK_OUTPUT`

Source: [`docs/usage/envs/LEFTHOOK_OUTPUT.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/envs/LEFTHOOK_OUTPUT.md).

Use `LEFTHOOK_OUTPUT={list of output values}` to specify what to print in your output. You can also set `LEFTHOOK_OUTPUT=false` to disable all output except for errors. Refer to the [`output`](configuration.md#doc-configuration-output) configuration option for more details.

<a id="doc-usage-envs-lefthook_output--example"></a>

#### Example

<!-- prettier-ignore -->
```bash
$ LEFTHOOK_OUTPUT=summary lefthook run pre-commit
summary: (done in 0.52 seconds)
✔️  lint
```

<a id="doc-usage-envs-lefthook_config"></a>

### `LEFTHOOK_CONFIG`

Source: [`docs/usage/envs/LEFTHOOK_CONFIG.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/envs/LEFTHOOK_CONFIG.md).

Override the main lefthook config with `LEFTHOOK_CONFIG=~/global_lefthook.yml`. Note: local config, specified extends, and remotes will still be loaded.

<a id="doc-usage-envs-lefthook_exclude"></a>

### `LEFTHOOK_EXCLUDE`

Source: [`docs/usage/envs/LEFTHOOK_EXCLUDE.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/envs/LEFTHOOK_EXCLUDE.md).

Use `LEFTHOOK_EXCLUDE={list of tags or command names to be excluded}` to skip some commands or scripts by tag or name (for commands only). See the [`exclude_tags`](configuration.md#doc-configuration-exclude_tags) configuration option for more details.

<a id="doc-usage-envs-lefthook_exclude--example"></a>

#### Example

<!-- prettier-ignore -->
```bash
LEFTHOOK_EXCLUDE=ruby,security,lint git commit -am "Skip some tag checks"
```

<a id="doc-usage-envs-lefthook_bin"></a>

### `LEFTHOOK_BIN`

Source: [`docs/usage/envs/LEFTHOOK_BIN.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/envs/LEFTHOOK_BIN.md).

Set `LEFTHOOK_BIN` to a location where lefthook is installed to use that instead of trying to detect from the it the PATH or from a package manager.

Useful for cases when:

- lefthook is installed multiple ways, and you want to be explicit about which one is used (example: installed through homebrew, but also is in Gemfile but you are using a ruby version manager like rbenv that prepends it to the path)
- debugging and/or developing lefthook

<a id="doc-usage-envs-clicolor_force"></a>

### `CLICOLOR_FORCE`

Source: [`docs/usage/envs/CLICOLOR_FORCE.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/envs/CLICOLOR_FORCE.md).

Set `CLICOLOR_FORCE=true` to force colored output in lefthook and all subcommands.

<a id="doc-usage-envs-no_color"></a>

### `NO_COLOR`

Source: [`docs/usage/envs/NO_COLOR.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/envs/NO_COLOR.md).

Set `NO_COLOR=true` to disable colored output in lefthook and all subcommands that lefthook calls.

<a id="doc-usage-envs-ci"></a>

### `CI`

Source: [`docs/usage/envs/CI.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/envs/CI.md).

When using NPM package `lefthook`, set `CI=true` in your CI (if it does not set it automatically) to prevent lefthook from installing hooks in the postinstall script:

<!-- prettier-ignore -->
```bash
CI=true npm install
CI=true yarn install
CI=true pnpm install
```

> **Note**
>
> Set `LEFTHOOK=1` or `LEFTHOOK=true` to override this behavior and install hooks in the postinstall script (despite `CI=true`).

## Runtime features

<a id="doc-usage-features-local"></a>

### Local config

Source: [`docs/usage/features/local.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/features/local.md).

You can extend and override options of your main configuration with `lefthook-local.yml`. Don't forget to add the file to `.gitignore`.

You can also use `lefthook-local.yml` without a main config file. This is useful when you want to use lefthook locally without imposing it on your teammates.

<!-- prettier-ignore -->
```yml
# lefthook.yml (committed into your repo)

pre-commit:
  jobs:
    - name: linter
      run: yarn lint
    - name: tests
      run: yarn test
```

<!-- prettier-ignore -->
```yml
# lefthook-local.yml (ignored by git)

pre-commit:
  jobs:
    - name: tests
      skip: true # don't want to run tests on every commit
    - name: linter
      run: yarn lint {staged_files} # lint only staged files
```

<a id="doc-usage-features-git-args"></a>

### Capture ARGS from git in the script

Source: [`docs/usage/features/git-args.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/features/git-args.md).

Lefthook passes Git arguments to your commands and scripts.

<!-- prettier-ignore -->
```
├── .lefthook
│   └── prepare-commit-msg
│       └── message.sh
└── lefthook.yml
```

<!-- prettier-ignore -->
```yml
# lefthook.yml

prepare-commit-msg:
  jobs:
    - script: "message.sh"
      runner: bash
    - run: echo "Git args: {1} {2} {3}"
```

<!-- prettier-ignore -->
```bash
# .lefthook/prepare-commit-msg/message.sh

# Arguments get passed from Git

COMMIT_MSG_FILE=$1
COMMIT_SOURCE=$2
SHA1=$3

# ...
```

<a id="doc-usage-features-git-lfs"></a>

### Git LFS support

Source: [`docs/usage/features/git-lfs.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/features/git-lfs.md).

> **Note**
>
> If git-lfs binary is not installed and not required in your project, LFS hooks won't be executed, and you won't be warned about it.
>
> Git LFS hooks may be slow. Disable them with the global `skip_lfs: true` setting.

Lefthook runs LFS hooks internally for the following hooks:

- post-checkout
- post-commit
- post-merge
- pre-push

Errors are suppressed if git LFS is not required for the project. You can use [`LEFTHOOK_VERBOSE`](usage.md#doc-usage-envs-lefthook_verbose) ENV to make lefthook show git LFS output.

To avoid calling LFS hooks set [`skip_lfs: true`](configuration.md#doc-configuration-skip_lfs) in lefthook.yml or lefthook-local.yml

<a id="doc-usage-features-interactive"></a>

### Using an interactive command or script

Source: [`docs/usage/features/interactive.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/features/interactive.md).

When you need to interact with user – specify [`interactive: true`](configuration.md#doc-configuration-interactive). Lefthook will connect to the current TTY and forward it to your command's or script's stdin.

<a id="doc-usage-features-pass-stdin"></a>

### Pass stdin to a command or script

Source: [`docs/usage/features/pass-stdin.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/usage/features/pass-stdin.md).

When you need to read the data from stdin – specify [`use_stdin: true`](configuration.md#doc-configuration-use_stdin). This option is good when you write a command or script that receives data from git using stdin (for the `pre-push` hook, for example).
