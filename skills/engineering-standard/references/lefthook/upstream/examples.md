# Configuration examples

[Snapshot index](README.md) · Lefthook v2.1.14.

## Contents

- [Recipes](#recipes)
  - [lefthook-local.yml](#doc-examples-lefthook-local)
  - [Wrap commands in local config](#doc-examples-wrap-commands)
  - [Stage fixed files](#doc-examples-stage_fixed)
  - [Filters](#doc-examples-filters)
  - [Skip or run on condition](#doc-examples-skip)
  - [Remotes](#doc-examples-remotes)
  - [Commitlint and commitzen](#doc-examples-commitlint)

## Recipes

<a id="doc-examples-lefthook-local"></a>

### lefthook-local.yml

Source: [`docs/examples/lefthook-local.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/examples/lefthook-local.md).

> **Tip**
>
> You can put `lefthook-local.yml` into your `~/.gitignore`, so in every project you can have your local-only overrides.

`lefthook-local.yml` overrides and extends the configuration of your main `lefthook.yml`.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      run: bundle exec rubocop -- {staged_files}
      glob: "*.rb"
    check-links:
      run: lychee -- {staged_files}
```

<!-- prettier-ignore -->
```yml
# lefthook-local.yml

pre-commit:
  parallel: true # run all commands concurrently
  commands:
    lint:
      run: docker-compose run backend {cmd} # wrap the original command with docker-compose
    check-links:
      skip: true # skip checking links

# Add another hook
post-merge:
  files: "git diff-tree -r --name-only --no-commit-id ORIG_HEAD HEAD"
  commands:
    dependencies:
      glob: "Gemfile*"
      run: docker-compose run backend bundle install
```

---

<a id="doc-examples-lefthook-local--the-merged-config-lefthook-will-use"></a>

#### The merged config lefthook will use

<!-- prettier-ignore -->
```yml

pre-commit:
  parallel: true
  commands:
    lint:
      run: docker-compose run backend bundle exec rubocop -- {staged_files}
      glob: "*.rb"
    check-links:
      run: lychee -- {staged_files}
      skip: true

post-merge:
  files: "git diff-tree -r --name-only --no-commit-id ORIG_HEAD HEAD"
  commands:
    dependencies:
      glob: "Gemfile*"
      run: docker-compose run backend bundle install
```

<a id="doc-examples-wrap-commands"></a>

### Wrap commands in local config

Source: [`docs/examples/wrap-commands.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/examples/wrap-commands.md).

Wrapping some commands defined in a main config with `dip`[^doc-examples-wrap-commands-1].

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  jobs:
    - name: rubocop
      run: bundle exec rubocop -A -- {staged_files}
```

<!-- prettier-ignore -->
```yml
# lefthook-local.yml

pre-commit:
  jobs:
    - name: rubocop
      run: dip {cmd}
```

[^doc-examples-wrap-commands-1]: [dip](https://github.com/bibendi/dip) – dockerized dev experience with, similar to `docker-compose run`

<a id="doc-examples-stage_fixed"></a>

### Stage fixed files

Source: [`docs/examples/stage_fixed.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/examples/stage_fixed.md).

> Works only for `pre-commit` Git hook

Sometimes your linter fixes the changes and you usually want to commit them automatically. To enable auto-staging of the fixed files use [`stage_fixed`](configuration.md#doc-configuration-stage_fixed) option.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      run: yarn lint {staged_files} --fix
      stage_fixed: true
```

<a id="doc-examples-filters"></a>

### Filters

Source: [`docs/examples/filters.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/examples/filters.md).

Files passed to your hooks can be filtered with the following options

- [`glob`](configuration.md#doc-configuration-glob)
- [`exclude`](configuration.md#doc-configuration-exclude)
- [`file_types`](configuration.md#doc-configuration-file_types)
- [`root`](configuration.md#doc-configuration-root)

In this example all **staged files** will pass through these filters.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  commands:
    lint:
      run: yarn lint {staged_files} --fix
      glob: "*.{js,ts}"
      root: frontend
      exclude:
        - *.config.js
        - *.config.ts
      file_types:
        - not executable
```

Imagine you've staged the following files

<!-- prettier-ignore -->
```bash
backend/asset.js
frontend/src/index.ts
frontend/bin/cli.js # <- executable
frontend/eslint.config.js
frontend/README.md
```

After all filters applied the `lint` command will execute the following:

<!-- prettier-ignore -->
```bash
yarn lint frontend/src/index.ts --fix
```

<a id="doc-examples-skip"></a>

### Skip or run on condition

Source: [`docs/examples/skip.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/examples/skip.md).

Here are two hooks.

`pre-commit` hook will only be executed when you're committing something on a branch starting with `dev/` prefix.

In `pre-push` hook:

- `test` command will be skipped if `NO_TEST` env variable is set to `1`
- `lint` command will only be executed if you're pushing the `main` branch

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  only:
    - ref: dev/*
  commands:
    lint:
      run: yarn lint {staged_files} --fix
      glob: "*.{ts,js}"
    test:
      run: yarn test

pre-push:
  commands:
    test:
      run: yarn test
      skip:
        - run: test "$NO_TEST" -eq 1
    lint:
      run: yarn lint
      only:
        - ref: main
```

<a id="doc-examples-remotes"></a>

### Remotes

Source: [`docs/examples/remotes.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/examples/remotes.md).

Use configurations from other Git repositories via `remotes` feature.

Lefthook will automatically download the remote config files and merge them into existing configuration.

<!-- prettier-ignore -->
```yml
remotes:
  - git_url: https://github.com/evilmartians/lefthook
    configs:
      - examples/remote/ping.yml
```

<a id="doc-examples-commitlint"></a>

### Commitlint and commitzen

Source: [`docs/examples/commitlint.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/examples/commitlint.md).

Use lefthook to generate commit messages using commitzen and validate them with commitlint.

<a id="doc-examples-commitlint--install-dependencies"></a>

#### Install dependencies

<!-- prettier-ignore -->
```bash
yarn add -D @commitlint/cli @commitlint/config-conventional

# For commitzen
yarn add -D commitizen cz-conventional-changelog
```

<a id="doc-examples-commitlint--configure"></a>

#### Configure

Setup `commitlint.config.js`. Conventional configuration:

<!-- prettier-ignore -->
```js
// commitlint.config.js

module.exports = {extends: ['@commitlint/config-conventional']};
```

If you are using commitzen, make sure to add this in `package.json`:

<!-- prettier-ignore -->
```json
"config": {
  "commitizen": {
    "path": "./node_modules/cz-conventional-changelog"
  }
}
```

Configure lefthook:

<!-- prettier-ignore -->
```yml
# lefthook.yml

# Build commit messages
prepare-commit-msg:
  commands:
    commitzen:
      interactive: true
      run: yarn run cz --hook # Or npx cz --hook
      env:
        LEFTHOOK: "0"

# Validate commit messages
commit-msg:
  commands:
    "lint commit message":
      run: yarn run commitlint --edit {1}
```

<a id="doc-examples-commitlint--test-it"></a>

#### Test it

<!-- prettier-ignore -->
```bash
# You can type it without message, if you are using commitzen
git commit

# Or provide a commit message is using only commitlint
git commit -am 'fix: typo'
```
