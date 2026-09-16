# Configuration reference

[Snapshot index](README.md) · Lefthook v2.1.14.

## Contents

- [Configuration files](#configuration-files)
  - [Config file name](#doc-configuration)
- [Global options](#global-options)
  - [`min_version`](#doc-configuration-min_version)
  - [`lefthook`](#doc-configuration-lefthook)
  - [`assert_lefthook_installed`](#doc-configuration-assert_lefthook_installed)
  - [`no_auto_install`](#doc-configuration-no_auto_install)
  - [`install_non_git_hooks`](#doc-configuration-install_non_git_hooks)
  - [`ai` 🧪 (beta)](#doc-configuration-ai)
  - [`extends`](#doc-configuration-extends)
  - [`glob_matcher`](#doc-configuration-glob_matcher)
  - [`colors`](#doc-configuration-colors)
  - [`output`](#doc-configuration-output)
  - [`no_tty`](#doc-configuration-no_tty)
  - [`rc`](#doc-configuration-rc)
  - [`source_dir`](#doc-configuration-source_dir)
  - [`source_dir_local`](#doc-configuration-source_dir_local)
  - [`skip_lfs`](#doc-configuration-skip_lfs)
  - [`templates`](#doc-configuration-templates)
- [Remote configuration](#remote-configuration)
  - [`remotes`](#doc-configuration-remotes)
  - [`git_url`](#doc-configuration-git_url)
  - [`ref`](#doc-configuration-ref)
  - [`refetch`](#doc-configuration-refetch)
  - [`refetch_frequency`](#doc-configuration-refetch_frequency)
  - [`configs`](#doc-configuration-configs)
- [Hooks and execution flow](#hooks-and-execution-flow)
  - [Git hook](#doc-configuration-hook)
  - [`parallel`](#doc-configuration-parallel)
  - [`piped`](#doc-configuration-piped)
  - [`follow`](#doc-configuration-follow)
  - [`files` (hook-level)](#doc-configuration-files-global)
  - [`fail_on_changes`](#doc-configuration-fail_on_changes)
  - [`fail_on_changes_diff`](#doc-configuration-fail_on_changes_diff)
  - [`exclude_tags`](#doc-configuration-exclude_tags)
  - [`setup`](#doc-configuration-setup)
- [Jobs, commands, and scripts](#jobs-commands-and-scripts)
  - [`jobs`](#doc-configuration-jobs)
  - [`name`](#doc-configuration-name)
  - [`run`](#doc-configuration-run)
  - [`script`](#doc-configuration-script)
  - [`runner`](#doc-configuration-runner)
  - [`args`](#doc-configuration-args)
  - [`group`](#doc-configuration-group)
  - [`commands`](#doc-configuration-commands)
  - [Scripts](#doc-configuration-scripts)
- [File selection and job options](#file-selection-and-job-options)
  - [`glob`](#doc-configuration-glob)
  - [`files` (job-level)](#doc-configuration-files)
  - [`file_types`](#doc-configuration-file_types)
  - [`root`](#doc-configuration-root)
  - [`exclude`](#doc-configuration-exclude)
  - [`skip`](#doc-configuration-skip)
  - [`only`](#doc-configuration-only)
  - [`tags`](#doc-configuration-tags)
  - [`env`](#doc-configuration-env)
  - [`fail_text`](#doc-configuration-fail_text)
  - [`stage_fixed`](#doc-configuration-stage_fixed)
  - [`interactive`](#doc-configuration-interactive)
  - [`use_stdin`](#doc-configuration-use_stdin)
  - [`priority`](#doc-configuration-priority)

## Configuration files

<a id="doc-configuration"></a>

### Config file name

Source: [`docs/configuration.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration.md).

Lefthook supports the following file names for the main config:

| Format | Acceptable config names                                                                                        |
| ------ | -------------------------------------------------------------------------------------------------------------- |
| YAML   | `lefthook.yml` `lefthook.yaml` `.lefthook.yml` `.lefthook.yaml` `.config/lefthook.yml` `.config/lefthook.yaml` |
| TOML   | `lefthook.toml` `.lefthook.toml` `.config/lefthook.toml`                                                       |
| JSON   | `lefthook.json` `.lefthook.json` `.config/lefthook.json`                                                       |
| JSONC  | `lefthook.jsonc` `.lefthook.jsonc` `.config/lefthook.jsonc`                                                    |

If there are more than 1 file in the project, only one will be used, and you'll never know which one. So, please, use one format in a project.

Filenames without the leading dot will also be looked up from the [`.config` subdirectory](https://github.com/pi0/config-dir).

Lefthook also merges an extra config with the name `lefthook-local`. All supported formats can be applied to this `-local` config. If you name your main config with the leading dot, like `.lefthook.json`, the `-local` config also must be named with the leading dot: `.lefthook-local.json`.

The `-local` config can be used without a main config file. This is useful when you want to use lefthook locally without imposing it on your teammates – just create a `lefthook-local.yml` file and add it to your global `.gitignore`.

## Global options

<a id="doc-configuration-min_version"></a>

### `min_version`

Source: [`docs/configuration/min_version.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/min_version.md).

If you want to specify a minimum version for lefthook binary (e.g. if you need some features older versions don't have) you can set this option.

<a id="doc-configuration-min_version--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

min_version: 1.1.3
```

<a id="doc-configuration-lefthook"></a>

### `lefthook`

Source: [`docs/configuration/lefthook.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/lefthook.md).

**Default:** `null`

> **New feature**
>
> Added in lefthook `1.10.5`

Provide a full path to lefthook executable or a command to run lefthook. Bourne shell (`sh`) syntax is supported.

> **Warning**
>
> This option does not merge from `remotes` or `extends` for security reasons. It does get merged from `lefthook-local.yml` if specified.

There are three reasons you may want to specify `lefthook`:

1. You want to force using specific lefthook version from your dependencies (e.g. npm package)
1. You use PnP loader for your JS/TS project, and your `package.json` with lefthook dependency locates in a subfolder
1. You want to make sure you use concrete lefthook executable path and want to defined it in `lefthook-local.yml`

<a id="doc-configuration-lefthook--specify-lefthook-executable"></a>

#### Specify lefthook executable

<!-- prettier-ignore -->
```yml
# lefthook.yml

lefthook: /usr/bin/lefthook

pre-commit:
  jobs:
    - run: yarn lint
```

<a id="doc-configuration-lefthook--specify-a-command-to-run-lefthook"></a>

#### Specify a command to run lefthook

<!-- prettier-ignore -->
```yml
# lefthook.yml

lefthook: |
  cd project-with-lefthook
  pnpm lefthook

pre-commit:
  jobs:
    - run: yarn lint
      root: project-with-lefthook
```

<a id="doc-configuration-lefthook--force-using-a-version-from-rubygems"></a>

#### Force using a version from Rubygems

<!-- prettier-ignore -->
```yml
# lefthook.yml

lefthook: bundle exec lefthook

pre-commit:
  jobs:
    - run: bundle exec rubocop -- {staged_files}
```

<a id="doc-configuration-lefthook--enable-debug-logs"></a>

#### Enable debug logs

<!-- prettier-ignore -->
```yml
# lefthook-local.yml

lefthook: LEFTHOOK_VERBOSE=1 lefthook
```

<a id="doc-configuration-assert_lefthook_installed"></a>

### `assert_lefthook_installed`

Source: [`docs/configuration/assert_lefthook_installed.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/assert_lefthook_installed.md).

**Default: `false`**

When set to `true`, fail (with exit status 1) if `lefthook` executable can't be found in $PATH, under node_modules/, as a Ruby gem, or other supported method. This makes sure git hook won't omit `lefthook` rules if `lefthook` ever was installed.

<a id="doc-configuration-assert_lefthook_installed--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

assert_lefthook_installed: true
```

<a id="doc-configuration-no_auto_install"></a>

### `no_auto_install`

Source: [`docs/configuration/no_auto_install.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/no_auto_install.md).

**Default: `false`**

Disable automatic installation and synchronization of git hooks when running lefthook. By default, lefthook automatically installs and updates hooks when you run `lefthook run` if the configuration has changed. Setting this to `true` disables that behavior.

This can also be controlled with the `--no-auto-install` option for the `lefthook run` command.

<a id="doc-configuration-no_auto_install--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

no_auto_install: true

pre-commit:
  commands:
    lint:
      run: npm run lint
```

<a id="doc-configuration-install_non_git_hooks"></a>

### `install_non_git_hooks`

Source: [`docs/configuration/install_non_git_hooks.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/install_non_git_hooks.md).

> **New feature**
>
> Added in lefthook `2.0.17`

Install non-Git hooks into `.git/hooks`. May be useful for using with tools like https://git-flow.sh/.

<a id="doc-configuration-ai"></a>

### `ai` 🧪 (beta)

Source: [`docs/configuration/ai.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/ai.md).

> This is a beta feature and still in development.

Declare LLM agent hooks directly in `lefthook.yml`. During `lefthook install`, lefthook generates the provider-specific settings file so that the agent calls `lefthook run <hook>` when the event fires.

Each sub-key is a provider name. Its value is a map from the provider's **event name** to a **lefthook hook name** defined elsewhere in the same config.

<a id="doc-configuration-ai--supported-providers"></a>

#### Supported providers

| Provider  | Generated file                | Docs                                                                                                       |
| --------- | ----------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `claude`  | `.claude/settings.json`       | [Claude Code hooks](https://code.claude.com/docs/en/hooks.md)                                              |
| `codex`   | `.codex/hooks.json`           | [Codex CLI hooks](https://developers.openai.com/codex/hooks)                                               |
| `cursor`  | `.cursor/hooks.json`          | [Cursor hooks](https://cursor.com/docs/agent/hooks)                                                        |
| `copilot` | `.github/hooks/lefthook.json` | [GitHub Copilot hooks](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/use-hooks) |

Keys under each provider must be that provider's hook event names. See the provider's hooks documentation for the supported events and their behaviour.

<a id="doc-configuration-ai--install-and-uninstall-behaviour"></a>

#### Install and uninstall behaviour

Claude, Codex, and Cursor preserve user-authored entries in their settings files. On `lefthook install`, old lefthook-managed entries are replaced with fresh ones derived from the current config. On `lefthook uninstall`, lefthook-managed entries are stripped while user-authored entries stay intact.

Copilot is handled differently: `lefthook install` rewrites `.github/hooks/lefthook.json` from scratch, and `lefthook uninstall` removes that file entirely.

Generated hook commands use the `lefthook` config value when set, otherwise the absolute path of the lefthook binary that ran `install` (via `os.Executable()`), so AI tools do not depend on `lefthook` being on `PATH`.

<a id="doc-configuration-ai--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

ai:
  claude:
    Stop: validate
    PreToolUse: security-check
  codex:
    Stop: validate
  cursor:
    stop: validate
    preToolUse: security-check
  copilot:
    postToolUse: validate

validate:
  jobs:
    - run: go test ./...

security-check:
  jobs:
    - run: ./scripts/security.sh
```

Running `lefthook install` creates (or updates) `.claude/settings.json`:

<!-- prettier-ignore -->
```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "lefthook run validate" }
        ]
      }
    ],
    "PreToolUse": [
      {
        "hooks": [
          { "type": "command", "command": "lefthook run security-check" }
        ]
      }
    ]
  }
}
```

And `.codex/hooks.json`:

<!-- prettier-ignore -->
```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "lefthook run validate" }
        ]
      }
    ]
  }
}
```

And `.cursor/hooks.json`:

<!-- prettier-ignore -->
```json
{
  "version": 1,
  "hooks": {
    "stop": [
      { "command": "lefthook run validate" }
    ],
    "preToolUse": [
      { "command": "lefthook run security-check" }
    ]
  }
}
```

And `.github/hooks/lefthook.json`:

<!-- prettier-ignore -->
```json
{
  "version": 1,
  "hooks": {
    "postToolUse": [
      { "command": "lefthook run validate" }
    ]
  }
}
```

<a id="doc-configuration-extends"></a>

### `extends`

Source: [`docs/configuration/extends.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/extends.md).

You can extend your config with another one YAML file. Its content will be merged. Extends for `lefthook.yml`, `lefthook-local.yml`, and [`remotes`](configuration.md#doc-configuration-remotes) configs are handled separately, so you can have different extends in these files.

You can use asterisk to make a glob.

<a id="doc-configuration-extends--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

extends:
  - /home/user/work/lefthook-extend.yml
  - /home/user/work/lefthook-extend-2.yml
  - lefthook-extends/file.yml
  - ../extend.yml
  - projects/*/specific-lefthook-config.yml
```

> **Note**
>
> Settings are applied in this order:
>
> - `lefthook.yml` – main config file
> - `extends` – configs specified in [extends](configuration.md#doc-configuration-extends) option
> - `remotes` – configs specified in [remotes](configuration.md#doc-configuration-remotes) option
> - `lefthook-local.yml` – local config file
>
> So, `extends` override settings from `lefthook.yml`, `remotes` override `extends`, and `lefthook-local.yml` can override everything.

<a id="doc-configuration-glob_matcher"></a>

### `glob_matcher`

Source: [`docs/configuration/glob_matcher.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/glob_matcher.md).

Configure which glob matching engine lefthook uses to filter files.

**Values:**

- `gobwas` (default): see https://github.com/gobwas/glob
- `doublestar`: Usual glob behavior (like in Bash)

<a id="doc-configuration-glob_matcher--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

glob_matcher: doublestar

pre-commit:
  jobs:
    - name: lint
      run: yarn eslint {staged_files}
      glob: "**/*.{js,ts}"
```

<a id="doc-configuration-glob_matcher--behaviour-comparison"></a>

#### Behaviour comparison

<!-- prettier-ignore -->
```yml
# gobwas (default): **/*.js matches src/app.js but NOT app.js
# doublestar:       **/*.js matches app.js, src/app.js, a/b/c/app.js
```

Use `doublestar` when migrating from other tools or when you need `**` to match files at any depth including the root. The setting applies globally to all `glob` and `exclude` patterns and is backwards compatible.

<a id="doc-configuration-colors"></a>

### `colors`

Source: [`docs/configuration/colors.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/colors.md).

**Default: `auto`**

Whether enable or disable colorful output of Lefthook. This option can be overwritten with `--colors` option. You can also provide your own color codes.

With the default `auto` value colors are enabled only when Lefthook detects a color capable terminal. Setting the option (or `--colors`) to `on` forces colors even when the output is not a terminal, e.g. in CI.

<a id="doc-configuration-colors--example"></a>

#### Example

Disable colors.

<!-- prettier-ignore -->
```yml
# lefthook.yml

colors: false
```

Custom color codes. Can be hex or ANSI codes.

<!-- prettier-ignore -->
```yml
# lefthook.yml

colors:
  cyan: 14
  gray: 244
  green: '#32CD32'
  red: '#FF1493'
  yellow: '#F0E68C'
```

Control via ENV variable.

- Set `NO_COLOR=true` to disable colored output in lefthook and all subcommands that lefthook calls.
- Set `CLICOLOR_FORCE=true` to force colored output in lefthook and all subcommands.

<a id="doc-configuration-output"></a>

### `output`

Source: [`docs/configuration/output.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/output.md).

You can manage verbosity using the `output` config. You can specify what to print in your output by setting these values, which you need to have

Possible values are `meta,summary,success,failure,execution,execution_out,execution_info,skips`.
By default, all output values are enabled

You can also disable all output with setting `output: false`. In this case only errors will be printed.

<a id="doc-configuration-output--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

output:
  - meta           # Print lefthook version
  - summary        # Print summary block (successful and failed steps)
  - empty_summary  # Print summary heading when there are no steps to run
  - success        # Print successful steps
  - failure        # Print failed steps printing
  - execution      # Print any execution logs
  - execution_out  # Print execution output
  - execution_info # Print `EXECUTE > ...` logging
  - skips          # Print "skip" (i.e. no files matched)
```

You can also override this list with the environment variable `LEFTHOOK_OUTPUT`:

<!-- prettier-ignore -->
```bash
LEFTHOOK_OUTPUT="meta,success,summary" lefthook run pre-commit
```

<a id="doc-configuration-no_tty"></a>

### `no_tty`

Source: [`docs/configuration/no_tty.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/no_tty.md).

**Default: `false`**

Whether hide spinner and other interactive things. This can be also controlled with `--no-tty` option for `lefthook run` command.

<a id="doc-configuration-no_tty--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

no_tty: true
```

<a id="doc-configuration-rc"></a>

### `rc`

Source: [`docs/configuration/rc.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/rc.md).

Provide an [**rc**](https://www.baeldung.com/linux/rc-files) file, which is actually a simple `sh` script. Currently it can be used to set ENV variables that are not accessible from non-shell programs.

<a id="doc-configuration-rc--example"></a>

#### Example

Use cases:

- You have a GUI program that runs git hooks (e.g., VSCode)
- You reference executables that are accessible only from a tweaked $PATH environment variable (e.g., when using rbenv or nvm, fnm)
- Or even if your GUI program cannot locate the `lefthook` executable :scream:
- Or if you want to use ENV variables that control the executables behavior in `lefthook.yml`

<!-- prettier-ignore -->
```bash
# An npm executable which is managed by nvm
$ which npm
/home/user/.nvm/versions/node/v15.14.0/bin/npm
```

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      run: npm run eslint {staged_files}
```

Provide a tweak to access `npm` executable the same way you do it in your ~/<shell>rc.

<!-- prettier-ignore -->
```yml
# lefthook-local.yml

# You can choose whatever name you want.
# You can share it between projects where you use lefthook.
# Make sure the path is absolute.
rc: ~/.lefthookrc
```

Or

<!-- prettier-ignore -->
```yml
# lefthook-local.yml

# If the path contains spaces, you need to quote it.
rc: '"${XDG_CONFIG_HOME:-$HOME/.config}/lefthookrc"'
```

In the rc file, export any new environment variables or modify existing ones.

<!-- prettier-ignore -->
```bash
# ~/.lefthookrc

# An nvm way
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# An fnm way
export FNM_DIR="$HOME/.fnm"
[ -s "$FNM_DIR/fnm.sh" ] && \. "$FNM_DIR/fnm.sh"

# Or maybe just
PATH=$PATH:$HOME/.nvm/versions/node/v15.14.0/bin
```

<!-- prettier-ignore -->
```bash
# Make sure you updated git hooks. This is important.
$ lefthook install -f
```

Now any program that runs your hooks will have a tweaked PATH environment variable and will be able to get `nvm` :wink:

<a id="doc-configuration-source_dir"></a>

### `source_dir`

Source: [`docs/configuration/source_dir.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/source_dir.md).

**Default: `.lefthook/`**

Change a directory for script files. The directory contains subfolders named after git hooks, each containing script files.

<a id="doc-configuration-source_dir--example"></a>

#### Example

<!-- prettier-ignore -->
```
.lefthook/
├── pre-commit/
│   ├── lint.sh
│   └── test.py
└── pre-push/
    └── check-files.rb
```

<a id="doc-configuration-source_dir_local"></a>

### `source_dir_local`

Source: [`docs/configuration/source_dir_local.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/source_dir_local.md).

**Default: `.lefthook-local/`**

Change a directory for _local_ script files (not stored in VCS).

This option is useful if you have a `lefthook-local.yml` config file and want to reference different scripts there.

<a id="doc-configuration-source_dir_local--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook-local.yml

source_dir_local: .lefthook-local/
```

<a id="doc-configuration-skip_lfs"></a>

### `skip_lfs`

Source: [`docs/configuration/skip_lfs.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/skip_lfs.md).

**Default:** `false`

Skip running LFS hooks even if it exists on your system.

<a id="doc-configuration-skip_lfs--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

skip_lfs: true

pre-push:
  commands:
    test:
      run: yarn test
```

<a id="doc-configuration-templates"></a>

### `templates`

Source: [`docs/configuration/templates.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/templates.md).

> **New feature**
>
> Added in lefthook `1.10.8`

Provide custom replacement for templates in `run` values.

With `templates` you can specify what can be overridden via `lefthook-local.yml` without a need to overwrite every jobs in your configuration.

<a id="doc-configuration-templates--override-with-lefthook-localyml"></a>

#### Override with lefthook-local.yml

<!-- prettier-ignore -->
```yml
# lefthook.yml

templates:
  dip: # empty

pre-commit:
  jobs:
    # Will run: `bundle exec rubocop -- file1 file2 file3 ...`
    - run: "{dip} bundle exec rubocop -- {staged_files}"
```

<!-- prettier-ignore -->
```yml
# lefthook-local.yml

templates:
  dip: dip # Will run: `dip bundle exec rubocop -- file1 file2 file3 ...`
```

<a id="doc-configuration-templates--reduce-redundancy"></a>

#### Reduce redundancy

<!-- prettier-ignore -->
```yml
# lefthook.yml

templates:
  wrapper: docker-compose run --rm -v $(pwd):/app service

pre-commit:
  jobs:
    - run: "{wrapper} yarn format"
    - run: "{wrapper} yarn lint"
    - run: "{wrapper} yarn test"
```

## Remote configuration

<a id="doc-configuration-remotes"></a>

### `remotes`

Source: [`docs/configuration/remotes.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/remotes.md).

You can provide multiple remote configs if you want to share yours lefthook configurations across many projects. Lefthook will automatically download and merge configurations into your local `lefthook.yml`.

You can use [`extends`](configuration.md#doc-configuration-extends) but the paths must be relative to the remote repository root.

If you provide [`scripts`](configuration.md#doc-configuration-scripts) in a remote config file, the [script `source_dir`](configuration.md#doc-configuration-source_dir) must also be in the **root of the remote repository**.

> **Note**
>
> Configs are merged in this order: `lefthook.yml` → `remotes` → `lefthook-local.yml`. For simplicity, keep jobs in remote configs independent from other steps.

<a id="doc-configuration-remotes--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

remotes:
  - git_url: git@github.com:evilmartians/lefthook
    ref: v1.0.0
    configs:
      - examples/ruby-linter.yml
```

<a id="doc-configuration-git_url"></a>

### `git_url`

Source: [`docs/configuration/git_url.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/git_url.md).

A URL to Git repository. It will be accessed with privileges of the machine lefthook runs on.

<a id="doc-configuration-git_url--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

remotes:
  - git_url: git@github.com:evilmartians/lefthook
```

Or

<!-- prettier-ignore -->
```yml
# lefthook.yml

remotes:
  - git_url: https://github.com/evilmartians/lefthook
```

<a id="doc-configuration-ref"></a>

### `ref`

Source: [`docs/configuration/ref.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/ref.md).

An optional _branch_ or _tag_ name.

> **Note**
>
> If you initially had `ref` option, ran `lefthook install`, and then removed it, lefthook won't decide which branch/tag to use as a ref. So, if you added it once, please, use it always to avoid issues in local setups.

See also [`refetch_frequency`](configuration.md#doc-configuration-refetch_frequency).

<a id="doc-configuration-ref--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

remotes:
  - git_url: git@github.com:evilmartians/lefthook
    ref: v1.0.0
```

<a id="doc-configuration-refetch"></a>

### `refetch`

Source: [`docs/configuration/refetch.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/refetch.md).

**Default:** `false`

Force remote config refetching on every run. Lefthook will be refetching the specified remote every time it is called.

See [`refetch_frequency`](configuration.md#doc-configuration-refetch_frequency) for more flexible refetching options and additional considerations.

<a id="doc-configuration-refetch--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

remotes:
  - git_url: https://github.com/evilmartians/lefthook
    refetch: true
```

<a id="doc-configuration-refetch_frequency"></a>

### `refetch_frequency`

Source: [`docs/configuration/refetch_frequency.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/refetch_frequency.md).

**Default:** Not set

Specifies how frequently Lefthook should refetch the remote configuration. This can be set to `always`, `never` or a time duration like `24h`, `30m`, etc.

- When set to `always`, Lefthook will always refetch the remote configuration on each run.
- When set to a duration (e.g., `24h`), Lefthook will check the last fetch time and refetch the configuration only if the specified amount of time has passed.
- When set to `never` or not set, Lefthook will not fetch from remote.

It is recommended to configure remotes that point to mutable references
(including ones without a `ref`) to be refetched with some frequency appropriate for the project.

Failure to fetch does not cause an error, but just a warning message.
If a successfully fetched previous configuration exists, it will be used.
Otherwise, the remote will be ignored.

<a id="doc-configuration-refetch_frequency--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

remotes:
  - git_url: https://github.com/evilmartians/lefthook
    refetch_frequency: 24h # Refetches once every 24 hours
```

> **Warning**
>
> If [`refetch`](configuration.md#doc-configuration-refetch) is set to `true`, it overrides any setting in `refetch_frequency`.

<a id="doc-configuration-configs"></a>

### `configs`

Source: [`docs/configuration/configs.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/configs.md).

**Default:** `[lefthook.yml]`

An optional array of config paths from remote's root.

<a id="doc-configuration-configs--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

remotes:
  - git_url: git@github.com:evilmartians/lefthook
    ref: v1.0.0
    configs:
      - examples/ruby-linter.yml
      - examples/test.yml
```

Example with multiple remotes merging multiple configurations.

<!-- prettier-ignore -->
```yml
# lefthook.yml

remotes:
  - git_url: git@github.com:org/lefthook-configs
    ref: v1.0.0
    configs:
      - examples/ruby-linter.yml
      - examples/test.yml
  - git_url: https://github.com/org2/lefthook-configs
    configs:
      - lefthooks/pre_commit.yml
      - lefthooks/post_merge.yml
  - git_url: https://github.com/org3/lefthook-configs
    ref: feature/new
    configs:
      - configs/pre-push.yml

```

## Hooks and execution flow

<a id="doc-configuration-hook"></a>

### Git hook

Source: [`docs/configuration/Hook.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/Hook.md).

Contains settings for the git hook (commands, scripts, skip rules, etc.). You can specify any Git hook or your own custom, e.g. `test`

<a id="doc-configuration-hook--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

# Git hook
pre-commit:
  jobs:
    - run: yarn lint {staged_files} --fix
      stage_fixed: true

# Custom hook
check-docs:
  jobs:
    - run: yarn check-docs
    - run: typos
```

<a id="doc-configuration-parallel"></a>

### `parallel`

Source: [`docs/configuration/parallel.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/parallel.md).

**Default: `false`**

> **Note**
>
> Lefthook runs commands and scripts **sequentially** by default

Run commands and scripts concurrently.

<a id="doc-configuration-parallel--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  parallel: true
  commands:
    lint:
      run: yarn lint
    test:
      run: yarn test
```

<a id="doc-configuration-piped"></a>

### `piped`

Source: [`docs/configuration/piped.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/piped.md).

**Default: `false`**

> **Note**
>
> Lefthook will return an error if both `piped: true` and `parallel: true` are set

Stop running commands and scripts if one of them fail.

<a id="doc-configuration-piped--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

database:
  piped: true # Stop if one of the steps fail
  commands:
    1_create:
      run: rake db:create
    2_migrate:
      run: rake db:migrate
    3_seed:
      run: rake db:seed
```

<a id="doc-configuration-follow"></a>

### `follow`

Source: [`docs/configuration/follow.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/follow.md).

**Default: `false`**

Follow the STDOUT of the running commands and scripts.

<a id="doc-configuration-follow--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-push:
  follow: true
  commands:
    backend-tests:
      run: bundle exec rspec
    frontend-tests:
      run: yarn test
```

> **Note**
>
> If used with [`parallel`](configuration.md#doc-configuration-parallel) the output can be a mess, so please avoid setting both options to `true`

<a id="doc-configuration-files-global"></a>

### `files` (hook-level)

Source: [`docs/configuration/files-global.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/files-global.md).

A custom command executed by the `sh` shell that returns the files or directories to be referenced in `{files}` template. See [`run`](configuration.md#doc-configuration-run) and [`files`](configuration.md#doc-configuration-files).

If the result of this command is empty, the execution of commands will be skipped.

<a id="doc-configuration-files-global--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  files: git diff --name-only master # custom list of files
  commands:
    ...
```

<a id="doc-configuration-fail_on_changes"></a>

### `fail_on_changes`

Source: [`docs/configuration/fail_on_changes.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/fail_on_changes.md).

The behaviour of lefthook when files (tracked by git) are modified can set by modifying the `fail_on_changes` configuration parameter. The possible values are:

- `never`: never exit with a non-zero status if files were modified (default).
- `always`: always exit with a non-zero status if files were modified.
- `ci`: exit with a non-zero status only when the `CI` environment variable is set. This can be useful when combined with `stage_fixed` to ensure a frictionless devX locally, and a robust CI.
- `non-ci`: exit with a non-zero status only when the `CI` environment variable is _not_ set. This can be useful in setups where the CI pipeline commits changes automatically, such as [autofix.ci](https://autofix.ci).

See also [`fail_on_changes_diff`](configuration.md#doc-configuration-fail_on_changes_diff).

<a id="doc-configuration-fail_on_changes--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml
pre-commit:
  parallel: true
  fail_on_changes: "always"
  commands:
    lint:
      run: yarn lint
    test:
      run: yarn test
```

<a id="doc-configuration-fail_on_changes_diff"></a>

### `fail_on_changes_diff`

Source: [`docs/configuration/fail_on_changes_diff.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/fail_on_changes_diff.md).

**Default:** outputs diff only in CI

When [`fail_on_changes`](configuration.md#doc-configuration-fail_on_changes) triggers, lefthook can optionally print a diff of the detected changes. Set this boolean to explicitly enable or disable the diff output regardless of environment.

<a id="doc-configuration-fail_on_changes_diff--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml
pre-commit:
  parallel: true
  fail_on_changes: "always"
  fail_on_changes_diff: true
  commands:
    lint:
      run: yarn lint
    test:
      run: yarn test
```

<a id="doc-configuration-exclude_tags"></a>

### `exclude_tags`

Source: [`docs/configuration/exclude_tags.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/exclude_tags.md).

[Tags](configuration.md#doc-configuration-tags) or command names that you want to exclude. This option can be overwritten with `LEFTHOOK_EXCLUDE` env variable.

<a id="doc-configuration-exclude_tags--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  exclude_tags: frontend
  commands:
    lint:
      tags: frontend
      ...
    test:
      tags: frontend
      ...
    check-syntax:
      tags: documentation
```

<!-- prettier-ignore -->
```bash
lefthook run pre-commit # will only run check-syntax command
```

> **Tip**
>
> Useful in `lefthook-local.yml` to skip specific commands locally without modifying the shared config.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-push:
  commands:
    packages-audit:
      tags:
        - frontend
        - security
      run: yarn audit
    gems-audit:
      tags:
        - backend
        - security
      run: bundle audit
```

You can skip commands by tags:

<!-- prettier-ignore -->
```yml
# lefthook-local.yml

pre-push:
  exclude_tags:
    - frontend
```

<a id="doc-configuration-setup"></a>

### `setup`

Source: [`docs/configuration/setup.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/setup.md).

> **New feature**
>
> Added in lefthook `2.1.2`

A list of instructions to run before any job. Supports templates and Git args like in [`run`](configuration.md#doc-configuration-run).

> **Note**
>
> When merging configs (with `lefthook-local.yml` or files from [`extends`](configuration.md#doc-configuration-extends)) `setup` instructions get **prepended**. When there are multiple `extends`, they get **appended** in the same order as extend files are specified.

<a id="doc-configuration-setup--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  setup:
    - run: |
        if ! command -v golangci-lint >/dev/null 2>&1; then
          go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.10.1
        fi
  jobs:
    - run: golangci-lint -- {staged_files}
      glob: "*.go"
```

## Jobs, commands, and scripts

<a id="doc-configuration-jobs"></a>

### `jobs`

Source: [`docs/configuration/jobs.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/jobs.md).

> **New feature**
>
> Added in lefthook `1.10.0`

Jobs provide a flexible way to define tasks, supporting both commands and scripts. Jobs can be grouped for advanced flow control.

Named jobs are merged across [`extends`](configuration.md#doc-configuration-extends) and local config; unnamed jobs are appended in definition order. Groups can include other jobs with their own parallel or piped flow — `glob`, `root`, `exclude`, `env`, and `files` on a group apply to all nested jobs.

<a id="doc-configuration-jobs--example"></a>

#### Example

> **Note**
>
> Currently, only `root`, `glob`, `exclude`, `env`, and `files` options are applied to group jobs. Other options must be set for each job individually. Submit a [feature request](https://github.com/evilmartians/lefthook/issues/new?assignees=&labels=feature+request&projects=&template=feature_request.md) if this limits your workflow.

A configuration demonstrating a piped group running in parallel with other jobs:

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  parallel: true
  jobs:
    - name: migrate
      root: backend/
      glob: "db/migrations/*"
      group:
        piped: true
        jobs:
          - run: bundle install
          - run: rails db:migrate
    - run: yarn lint --fix {staged_files}
      root: frontend/
      stage_fixed: true
    - run: bundle exec rubocop
      root: backend/
    - run: golangci-lint
      root: proxy/
    - script: verify.sh
      runner: bash
```

This configuration runs migrate jobs in a piped flow while other jobs execute in parallel.

<a id="doc-configuration-name"></a>

### `name`

Source: [`docs/configuration/name.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/name.md).

Name of a job. Will be printed in summary. If specified, the jobs can be merged with a jobs of the same name in a [local config](examples.md#doc-examples-lefthook-local) or [extends](configuration.md#doc-configuration-extends).

<a id="doc-configuration-name--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  jobs:
    - name: lint and fix
      run: yarn run eslint --fix {staged_files}
```

<a id="doc-configuration-run"></a>

### `run`

Source: [`docs/configuration/run.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/run.md).

This is a mandatory option for a command, which specifies the actual command to be run using the `sh` shell.

You can use files templates that will be substituted with the appropriate files on execution:

- `{files}` - custom [`files`](configuration.md#doc-configuration-files) command result.
- `{staged_files}` - staged files which you try to commit.
- `{push_files}` - files that are committed but not pushed.
- `{all_files}` - all files tracked by git.
- `{cmd}` - shorthand for the command from `lefthook.yml`.
- `{0}` - shorthand for the single space-joint string of git hook arguments.
- `{1}` - shorthand for the 1-st git hook argument (and so on for `{2}`, `{3}`, etc.)
- `{lefthook_job_name}` - current job/command/script name

> **Note**
>
> Command line length has a limit on every system. If your list of files is quite long, lefthook splits your files list to fit in the limit and runs few commands sequentially.

<a id="doc-configuration-run--example"></a>

#### Example

Run `yarn lint` on `pre-commit` hook.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      run: yarn lint
```

<a id="doc-configuration-run--files-template"></a>

#### `{files}` template

Run `go vet` only on files listed with `git ls-files -m` command with `.go` extension.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    govet:
      files: git ls-files -m
      glob: "*.go"
      run: go vet -- {files}
```

<a id="doc-configuration-run--staged_files"></a>

#### `{staged_files}`

Run `yarn eslint` only on staged files with `.js`, `.ts`, `.jsx`, and `.tsx` extensions.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    eslint:
      glob: "*.{js,ts,jsx,tsx}"
      run: yarn eslint {staged_files}
```

<a id="doc-configuration-run--push_files"></a>

#### `{push_files}`

If you want to lint files only before pushing them.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-push:
  commands:
    eslint:
      glob: "*.{js,ts,jsx,tsx}"
      run: yarn eslint {push_files}
```

<a id="doc-configuration-run--all_files"></a>

#### `{all_files}`

Simply run `bundle exec rubocop` on all files with `.rb` extension excluding `application.rb` and `routes.rb` files.

> **Note**
>
> `--force-exclusion` will apply `Exclude` configuration setting of Rubocop

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    rubocop:
      tags:
        - backend
        - style
      glob: "*.rb"
      exclude:
        - config/application.rb
        - config/routes.rb
      run: bundle exec rubocop --force-exclusion -- {all_files}
```

<a id="doc-configuration-run--cmd"></a>

#### `{cmd}`

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      run: yarn lint
  scripts:
    "good_job.js":
      runner: node
```

You can wrap it in docker runner locally:

<!-- prettier-ignore -->
```yml
# lefthook-local.yml

pre-commit:
  commands:
    lint:
      run: docker run -it --rm <container_id_or_name> {cmd}
  scripts:
    "good_job.js":
      runner: docker run -it --rm <container_id_or_name> {cmd}
```

<a id="doc-configuration-run--git-arguments"></a>

#### Git arguments

Prevent commits from containing multiple sign-offs.

<!-- prettier-ignore -->
```yml
# lefthook.yml

# Note: commit-msg hook takes a single parameter,
#       the name of the file that holds the proposed commit log message.
# Source: https://git-scm.com/docs/githooks#_commit_msg
commit-msg:
  commands:
    multiple-sign-off:
      run: 'test $(grep -c "^Signed-off-by: " {1}) -lt 2'
```

<a id="doc-configuration-run--rubocop"></a>

#### Rubocop

If using `{all_files}` with RuboCop, it will ignore RuboCop's `Exclude` configuration setting. To avoid this, pass `--force-exclusion`.

<a id="doc-configuration-run--quotes"></a>

#### Quotes

If you want to have all your files quoted with double quotes `"` or single quotes `'`, quote the appropriate shorthand:

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      glob: "*.js"
      # Quoting with double quotes `"` might be helpful for Windows users
      run: yarn eslint "{staged_files}" # will run `yarn eslint "file1.js" "file2.js" "[strange name].js"`
    test:
      glob: "*.{spec.js}"
      run: yarn test '{staged_files}' # will run `yarn eslint 'file1.spec.js' 'file2.spec.js' '[strange name].spec.js'`
    format:
      glob: "*.js"
      # Will quote where needed with single quotes
      run: yarn test {staged_files} # will run `yarn eslint file1.js file2.js '[strange name].spec.js'`
```

<a id="doc-configuration-run--scripts"></a>

#### Scripts

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  jobs:
    - name: a whole script in a run
      run: |
        for file in $(ls .); do
          yarn lint $file
        done
```

<a id="doc-configuration-script"></a>

### `script`

Source: [`docs/configuration/script.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/script.md).

Name of a script to execute. The rules are the same as for [`scripts`](configuration.md#doc-configuration-scripts)

Use [`args`](configuration.md#doc-configuration-args) to append arguments to the script. Configuring `args`
replaces arguments passed by Git unless the `{0}` template is included.

<a id="doc-configuration-script--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  jobs:
    - script: linter.sh
      runner: bash
      args: "{staged_files}"
```

<!-- prettier-ignore -->
```bash
# .lefthook/pre-commit/linter.sh

echo "Everything is OK"
```

<a id="doc-configuration-runner"></a>

### `runner`

Source: [`docs/configuration/runner.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/runner.md).

You should specify a runner for the script. This is a command that should execute a script file. It will be called the following way: `<runner> <path-to-script>` (e.g. `ruby .lefthook/pre-commit/lint.rb`).

<a id="doc-configuration-runner--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  scripts:
    "lint.js":
      runner: node
    "check.go":
      runner: go run
```

<a id="doc-configuration-args"></a>

### `args`

Source: [`docs/configuration/args.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/args.md).

> **New feature**
>
> Added in lefthook `2.0.5`

Sometimes you want to pass arguments to the scripts or be able to overwrite arguments to the commands in `lefthook-local.yml`. For this you can use `args` option which will simply be appended to the command. You can use the same templates as in [`run`](configuration.md#doc-configuration-run).

Arguments passed by Git will be omitted if you specify `args` in the config. Providing no `args` or providing `args: "{0}"` works the same way.

See [`run`](configuration.md#doc-configuration-run) for supported templates.

<a id="doc-configuration-args--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  jobs:
    - script: check-python-files.sh
      runner: bash
      args: "{staged_files}"
      glob: "*.py"

    - run: yarn lint
      args: "{staged_files}"
      glob:
        - "*.ts"
        - "*.js"
```

<a id="doc-configuration-group"></a>

### `group`

Source: [`docs/configuration/group.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/group.md).

You can define a group of jobs and configure how they should execute using the following options:

- [`parallel`](configuration.md#doc-configuration-parallel): Executes all jobs in the group simultaneously.
- [`piped`](configuration.md#doc-configuration-piped): Executes jobs sequentially, passing output between them.
- [`jobs`](configuration.md#doc-configuration-jobs): Specifies the jobs within the group.

<a id="doc-configuration-group--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  jobs:
    - group:
        parallel: true
        jobs:
          - run: echo 1
          - run: echo 2
          - run: echo 3
```

If you specify `env`, `root`, `glob`, `exclude`, or `files` on a group, they will be inherited to the underlying jobs.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  jobs:
    - env:
        E1: hello
      glob:
        - "*.md"
      exclude:
        - "README.md"
      root: "subdir/"
      group:
        parallel: true
        jobs:
          - run: echo $E1
          - run: echo $E1
            env:
              E1: bonjour
```

A `files` command set on a group is executed for every nested job that uses the `{files}` template. A nested job can define its own `files` to override it.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  jobs:
    - glob:
        - "*.py"
      files: git diff --name-only master
      group:
        jobs:
          - run: ruff check {files}
          - run: ruff format --check {files}
            files: git ls-files
```

> **Note**
>
> To make a group mergeable with settings defined in local config or extends you have to specify the name of the job group belongs to:
>
> <!-- prettier-ignore -->
> ```yml
> pre-commit:
>   jobs:
>     - name: a name of a group
>       group:
>         jobs:
>           - name: lint
>             run: yarn lint
>           - name: test
>             run: yarn test
> ```

<a id="doc-configuration-commands"></a>

### `commands`

Source: [`docs/configuration/Commands.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/Commands.md).

Commands to be executed for the hook. Each command has a name and associated run [options](configuration.md#doc-configuration-commands--command-options).

<a id="doc-configuration-commands--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      ... # command options
```

<a id="doc-configuration-commands--command-options"></a>

#### Command options

- [`run`](configuration.md#doc-configuration-run)
- [`skip`](configuration.md#doc-configuration-skip)
- [`only`](configuration.md#doc-configuration-only)
- [`tags`](configuration.md#doc-configuration-tags)
- [`glob`](configuration.md#doc-configuration-glob)
- [`files`](configuration.md#doc-configuration-files)
- [`file_types`](configuration.md#doc-configuration-file_types)
- [`env`](configuration.md#doc-configuration-env)
- [`root`](configuration.md#doc-configuration-root)
- [`exclude`](configuration.md#doc-configuration-exclude)
- [`fail_text`](configuration.md#doc-configuration-fail_text)
- [`stage_fixed`](configuration.md#doc-configuration-stage_fixed)
- [`interactive`](configuration.md#doc-configuration-interactive)
- [`use_stdin`](configuration.md#doc-configuration-use_stdin)
- [`priority`](configuration.md#doc-configuration-priority)

<a id="doc-configuration-scripts"></a>

### Scripts

Source: [`docs/configuration/Scripts.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/Scripts.md).

Scripts are stored under `<source_dir>/<hook-name>/` folder. These scripts are your own executables which are being run in the project root.

To add a script for a `pre-commit` hook:

1. Run `lefthook add -d pre-commit`
1. Edit `.lefthook/pre-commit/my-script.sh`
1. Add an entry to `lefthook.yml`

   <!-- prettier-ignore -->
   ```yml
   # lefthook.yml

   pre-commit:
     scripts:
       "my-script.sh":
         runner: bash
   ```

<a id="doc-configuration-scripts--example"></a>

#### Example

Let's create a bash script to check commit templates `.lefthook/commit-msg/template_checker`:

<!-- prettier-ignore -->
```bash
INPUT_FILE=$1
START_LINE=`head -n1 $INPUT_FILE`
PATTERN="^(TICKET)-[[:digit:]]+: "
if ! [[ "$START_LINE" =~ $PATTERN ]]; then
  echo "Bad commit message, see example: TICKET-123: some text"
  exit 1
fi
```

Now we can ask lefthook to run our bash script by adding this code to
`lefthook.yml` file:

<!-- prettier-ignore -->
```yml
# lefthook.yml

commit-msg:
  scripts:
    "template_checker":
      runner: bash
```

When you try to commit `git commit -m "bad commit text"` script `template_checker` will be executed. Since commit text doesn't match the described pattern the commit process will be interrupted.

Use [`args`](configuration.md#doc-configuration-args) to append arguments to a script. Arguments passed by
Git are omitted when `args` is configured, so use the `{0}` template if they
should be preserved.

<!-- prettier-ignore -->
```yml
commit-msg:
  scripts:
    "template_checker":
      runner: bash
      args: "{0}"
```

## File selection and job options

<a id="doc-configuration-glob"></a>

### `glob`

Source: [`docs/configuration/glob.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/glob.md).

You can set a glob to filter files for your command. This is only used if you use a file template in [`run`](configuration.md#doc-configuration-run) option or provide your custom [`files`](configuration.md#doc-configuration-files) command.

<a id="doc-configuration-glob--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  jobs:
    - name: lint
      run: yarn eslint {staged_files}
      glob: "*.{js,ts,jsx,tsx}"
```

> **Note**
>
> From lefthook version `1.10.10` you can also provide a list of globs:
>
> <!-- prettier-ignore -->
> ```yml
> # lefthook.yml
>
> pre-commit:
>   jobs:
>     - run: yarn lint {staged_files}
>       glob:
>         - "*.ts"
>         - "*.js"
> ```

For patterns that you can use see [this](https://tldp.org/LDP/GNU-Linux-Tools-Summary/html/x11655.htm) reference. We use [glob](https://github.com/gobwas/glob) library.

<a id="doc-configuration-glob--when-using-root"></a>

#### When using `root`

Globs are still calculated from the actual root of the git repo — `root` is ignored.

<a id="doc-configuration-glob--behaviour-of-"></a>

#### Behaviour of `**`

The `**` pattern matches **1 or more** directories deep (not zero or more, unlike most other tools). To match files at both the top level and nested, use separate patterns or opt-in to standard behavior with [`glob_matcher: doublestar`](configuration.md#doc-configuration-glob_matcher).

<!-- prettier-ignore -->
```yaml
glob: "src/**/*.js"  # does NOT match src/file.js
glob: "src/*.js"     # matches src/file.js only
```

<a id="doc-configuration-glob--using-glob-without-a-files-template-in-run"></a>

#### Using `glob` without a files template in `run`

If you've specified `glob` but don't have a files template in [`run`](configuration.md#doc-configuration-run) option, lefthook will check `{staged_files}` for `pre-commit` hook and `{push_files}` for `pre-push` hook and apply filtering. If no files left, the command will be skipped.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  jobs:
    - name: lint
      run: npm run lint # skipped if no .js files staged
      glob: "*.js"
```

<a id="doc-configuration-files"></a>

### `files` (job-level)

Source: [`docs/configuration/files.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/files.md).

A custom command executed by the `sh` shell that returns the files or directories to be referenced in `{files}` template for [`run`](configuration.md#doc-configuration-run) setting.

If the result of this command is empty, the execution of commands will be skipped.

This option overwrites the [hook-level `files`](configuration.md#doc-configuration-files-global) option.

<a id="doc-configuration-files--example"></a>

#### Example

Provide a git command to list files.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-push:
  commands:
    stylelint:
      tags:
        - frontend
        - style
      files: git diff --name-only master
      glob: "*.js"
      run: yarn stylelint {files}
```

Call a custom script for listing files.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-push:
  commands:
    rubocop:
      tags: backend
      glob: "**/*.rb"
      files: node ./lefthook-scripts/ls-files.js # you can call your own scripts
      run: bundle exec rubocop --force-exclusion --parallel -- {files}
```

<a id="doc-configuration-file_types"></a>

### `file_types`

Source: [`docs/configuration/file_types.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/file_types.md).

Filter files in a [`run`](configuration.md#doc-configuration-run) templates by their type. Special file types and MIME types are supported[^doc-configuration-file_types-1]:

| File type            | Explanation                                                       |
| -------------------- | ----------------------------------------------------------------- |
| `text`               | Any file that contains text. Symlinks are not followed.           |
| `binary`             | Any file that contains non-text bytes. Symlinks are not followed. |
| `executable`         | Any file that has executable bits set. Symlinks are not followed. |
| `not executable`     | Any file without executable bits in file mode. Symlinks included. |
| `symlink`            | A symlink file.                                                   |
| `not symlink`        | Any non-symlink file.                                             |
| `text/html`          | An HTML file.                                                     |
| `text/xml`           | An XML file.                                                      |
| `text/javascript`    | A Javascript file.                                                |
| `text/x-php`         | A PHP file.                                                       |
| `text/x-lua`         | A Lua file.                                                       |
| `text/x-perl`        | A Perl file.                                                      |
| `text/x-python`      | A Python file.                                                    |
| `text/x-shellscript` | Shell script file.                                                |
| `text/x-sh`          | Also shell script file.                                           |
| `application/json`   | JSON file.                                                        |

> **Note**
>
> The following types are applied using AND logic: `text`, `binary`, `executable`, `not executable`, `symlink`, `not symlink`.
>
> MIME types are applied using OR logic — you can combine `text/x-lua` and `text/x-sh`, but not `symlink` and `not symlink`.

<a id="doc-configuration-file_types--example"></a>

#### Example

Apply some different linters on text and binary files.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint-code:
      run: yarn lint {staged_files}
      file_types: text
    check-hex-codes:
      run: yarn check-hex {staged_files}
      file_types: binary
```

Skip symlinks.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      run: yarn lint --fix {staged_files}
      file_types:
        - not symlink
```

Lint executable scripts.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      run: yarn lint --fix {staged_files}
      file_types:
        - executable
        - text
```

Check typos in scripts.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  jobs:
    - run: typos -w -- {staged_files}
      file_types:
        - text/x-perl
        - text/x-python
        - text/x-php
        - text/x-lua
        - text/x-sh
```

[^doc-configuration-file_types-1]: All supported MIME types can be found here: [supported_mimes.md](https://github.com/gabriel-vasile/mimetype/blob/v1.4.11/supported_mimes.md)

<a id="doc-configuration-root"></a>

### `root`

Source: [`docs/configuration/root.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/root.md).

You can change the CWD for the command you execute using `root` option.

This is useful when you execute some `npm` or `yarn` command but the `package.json` is in another directory.

For `pre-push` and `pre-commit` hooks and for the custom `files` command `root` option is used to filter file paths. If all files are filtered the command will be skipped.

<a id="doc-configuration-root--example"></a>

#### Example

Format and stage files from a `client/` folder.

<!-- prettier-ignore -->
```bash
# Folders structure

$ tree .
.
├── client/
│   ├── package.json
│   ├── node_modules/
|   ├── ...
├── server/
|   ...
```

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      root: "client/"
      glob: "*.{js,ts}"
      run: yarn eslint --fix {staged_files} && git add {staged_files}
```

> **Note**
>
> Globs are always calculated from the actual root of the git repo — `root` does not affect glob matching.

<a id="doc-configuration-exclude"></a>

### `exclude`

Source: [`docs/configuration/exclude.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/exclude.md).

This option allows to setup a list of globs for files to be excluded in files template.

> **Note**
>
> The glob patterns used in `exclude` are affected by the [`glob_matcher`](configuration.md#doc-configuration-glob_matcher) setting. See the glob_matcher documentation for details on how `**` patterns behave.

<a id="doc-configuration-exclude--example"></a>

#### Example

Run Rubocop on staged files with `.rb` extension except for `application.rb`, `routes.rb`, `rails_helper.rb`, and all Ruby files in `config/initializers/`.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  jobs:
    - name: lint
      glob: "*.rb"
      exclude:
        - config/routes.rb
        - config/application.rb
        - config/initializers/*.rb
        - spec/rails_helper.rb
      run: bundle exec rubocop --force-exclusion -- {staged_files}
```

If you've specified `exclude` but don't have a files template in [`run`](configuration.md#doc-configuration-run) option, lefthook will check `{staged_files}` for `pre-commit` hook and `{push_files}` for `pre-push` hook and apply filtering. If no files left, the command will be skipped.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  exclude:
    - "*/application.rb"
  jobs:
    - name: lint
      run: bundle exec rubocop # will skip if only application.rb was staged
```

<a id="doc-configuration-skip"></a>

### `skip`

Source: [`docs/configuration/skip.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/skip.md).

You can skip all or specific commands and scripts using `skip` option. You can also skip when merging, rebasing, or being on a specific branch. Globs are available for branches.

Possible skip values:

- `rebase` - when in rebase git state
- `merge` - when in merge git state
- `merge-commit` - when current HEAD commit is the merge commit
- `ref: main` - when on a `main` branch
- `run: test ${SKIP_ME} -eq 1` - when `test ${SKIP_ME} -eq 1` is successful (return code is 0)

<a id="doc-configuration-skip--example"></a>

#### Example

Always skipping a command:

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      skip: true
      run: yarn lint
```

Skipping on merging and rebasing:

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      skip:
        - merge
        - rebase
      run: yarn lint
```

Or

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      skip: merge
      run: yarn lint
```

Skipping when your are on a merge commit:

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-push:
  commands:
    lint:
      skip: merge-commit
      run: yarn lint
```

Skipping the whole hook on `main` branch:

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  skip:
    - ref: main
  commands:
    lint:
      run: yarn lint
    test:
      run: yarn test
```

Skipping hook for all `dev/*` branches:

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  skip:
    - ref: dev/*
  commands:
    lint:
      run: yarn lint
    test:
      run: yarn test
```

Skipping hook by running a command:

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  skip:
    - run: test "${NO_HOOK}" -eq 1
  commands:
    lint:
      run: yarn lint
    test:
      run: yarn test
```

Skipping a command conditionally based on the existence of a CLI tool:

<!-- prettier-ignore -->
```yml
prepare-commit-msg:
  skip:
    - merge
    - rebase
  commands:
    aiautocommit:
      interactive: true
      run: aiautocommit commit --output-file "{1}"
      env:
        LOG_LEVEL: info
      skip:
        # only run this if the tool exists
        - run: "! which aiautocommit"
```

> **Tip**
>
> Always skipping is useful when you have a `lefthook-local.yml` config and you don't want to run some commands locally. So you just overwrite the `skip` option for them to be `true`.
>
> <!-- prettier-ignore -->
> ```yml
> # lefthook.yml
>
> pre-commit:
>   commands:
>     lint:
>       run: yarn lint
> ```
>
> <!-- prettier-ignore -->
> ```yml
> # lefthook-local.yml
>
> pre-commit:
>   commands:
>     lint:
>       skip: true
> ```

<a id="doc-configuration-only"></a>

### `only`

Source: [`docs/configuration/only.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/only.md).

You can force a command, script, or the whole hook to execute only in certain conditions. This option acts like the opposite of [`skip`](configuration.md#doc-configuration-skip). It accepts the same values but skips execution only if the condition is not satisfied.

> **Note**
>
> `skip` option takes precedence over `only` option, so if you have conflicting conditions the execution will be skipped.

<a id="doc-configuration-only--example"></a>

#### Example

Execute a hook only for `dev/*` branches.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  only:
    - ref: dev/*
  commands:
    lint:
      run: yarn lint
    test:
      run: yarn test
```

When rebasing execute quick linter but skip usual linter and tests.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      skip: rebase
      run: yarn lint
    test:
      skip: rebase
      run: yarn test
    lint-on-rebase:
      only: rebase
      run: yarn lint-quickly
```

<a id="doc-configuration-tags"></a>

### `tags`

Source: [`docs/configuration/tags.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/tags.md).

You can specify tags for commands and scripts. This is useful for [excluding](configuration.md#doc-configuration-exclude_tags). You can specify more than one tag using comma.

<a id="doc-configuration-tags--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      tags:
        - frontend
        - js
      run: yarn lint
    test:
      tags:
        - backend
        - ruby
      run: bundle exec rspec
```

<a id="doc-configuration-env"></a>

### `env`

Source: [`docs/configuration/env.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/env.md).

You can specify some ENV variables for the command or script.

<a id="doc-configuration-env--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    test:
      env:
        RAILS_ENV: test
      run: bundle exec rspec
```

<a id="doc-configuration-env--extending-path"></a>

#### Extending `PATH`

If your hook is run by a GUI program and you use PATH tweaks in your `~/.<shell>rc`, you might see an _executable not found_ error. You can extend `$PATH` via `lefthook-local.yml`:

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    test:
      run: yarn test
```

<!-- prettier-ignore -->
```yml
# lefthook-local.yml

pre-commit:
  commands:
    test:
      env:
        PATH: $PATH:/home/me/path/to/yarn
```

> **Tip**
>
> Useful when running lefthook across different OSes or shells where environment variables are set differently.

<a id="doc-configuration-fail_text"></a>

### `fail_text`

Source: [`docs/configuration/fail_text.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/fail_text.md).

You can specify a text to show when the command or script fails.

<a id="doc-configuration-fail_text--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      run: yarn lint
      fail_text: Add node executable to $PATH
```

<!-- prettier-ignore -->
```bash
$ git commit -m 'fix: Some bug'

Lefthook v1.1.3
RUNNING HOOK: pre-commit

  EXECUTE > lint

SUMMARY: (done in 0.01 seconds)
🥊  lint: Add node executable to $PATH env
```

<a id="doc-configuration-stage_fixed"></a>

### `stage_fixed`

Source: [`docs/configuration/stage_fixed.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/stage_fixed.md).

**Default: `false`**

> **Note**
>
> Works **only** for the `pre-commit` hook.

When set to `true` lefthook will automatically call `git add` on files after running the command or script. For a command if [`files`](configuration.md#doc-configuration-files) option was specified, the specified command will be used to retrieve files for `git add`. For scripts and commands without [`files`](configuration.md#doc-configuration-files) option `{staged_files}` template will be used. All filters ([`glob`](configuration.md#doc-configuration-glob), [`exclude`](configuration.md#doc-configuration-exclude)) will be applied if specified.

If the `git add` call fails, the hook fails too. Otherwise the commit would silently go through with the unfixed content.

<a id="doc-configuration-stage_fixed--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      run: npm run lint --fix {staged_files}
      stage_fixed: true
```

<a id="doc-configuration-interactive"></a>

### `interactive`

Source: [`docs/configuration/interactive.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/interactive.md).

**Default: `false`**

> **Note**
>
> If you want to pass stdin to your command or script but don't need to get the input from CLI, use [`use_stdin`](configuration.md#doc-configuration-use_stdin) option instead.

Whether to use interactive mode. This applies the certain behavior:

- All `interactive` commands/scripts are executed after non-interactive. Exception: [`piped`](configuration.md#doc-configuration-piped) option is set to `true`.
- When executing, lefthook tries to open /dev/tty (Linux/Unix only) and use it as stdin.
- When [`no_tty`](configuration.md#doc-configuration-no_tty) option is set, `interactive` is ignored.

<a id="doc-configuration-use_stdin"></a>

### `use_stdin`

Source: [`docs/configuration/use_stdin.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/use_stdin.md).

> **Note**
>
> With many commands or scripts having `use_stdin: true`, only one will receive the data. The others will have nothing. If you need to pass the data from stdin to every command or script, please, submit a [feature request](https://github.com/evilmartians/lefthook/issues/new?assignees=&labels=feature+request&projects=&template=feature_request.md).

Pass the stdin from the OS to the command/script.

<a id="doc-configuration-use_stdin--example"></a>

#### Example

Use this option for the `pre-push` hook when you have a script that does `while read ...`. Without this option lefthook will hang: lefthook uses [pseudo TTY](https://github.com/creack/pty) by default, and it doesn't close stdin when all data is read.

<!-- prettier-ignore -->
```bash
# .lefthook/pre-push/do-the-magic.sh

remote="$1"
url="$2"

while read local_ref local_oid remote_ref remote_oid; do
  # ...
done
```

<!-- prettier-ignore -->
```yml
# lefthook.yml
pre-push:
  scripts:
    "do-the-magic.sh":
      runner: bash
      use_stdin: true
```

<a id="doc-configuration-priority"></a>

### `priority`

Source: [`docs/configuration/priority.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/configuration/priority.md).

**Default: `0`**

> **Note**
>
> This option makes sense only when `parallel: false` or `piped: true` is set.
>
> Value `0` is considered an `+Infinity`, so commands or scripts with `priority: 0` or without this setting will be run at the very end.

Set priority from 1 to +Infinity. This option can be used to configure the order of the sequential steps.

<a id="doc-configuration-priority--example"></a>

#### Example

<!-- prettier-ignore -->
```yml
# lefthook.yml

post-checkout:
  piped: true
  commands:
    db-create:
      priority: 1
      run: rails db:create
    db-migrate:
      priority: 2
      run: rails db:migrate
    db-seed:
      priority: 3
      run: rails db:seed

  scripts:
    "check-spelling.sh":
      runner: bash
      priority: 1
    "check-grammar.rb":
      runner: ruby
      priority: 2
```
