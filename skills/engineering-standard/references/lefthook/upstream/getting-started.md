# Getting started and installation

[Snapshot index](README.md) · Lefthook v2.1.14.

## Contents

- [Overview](#overview)
  - [What is Lefthook?](#doc-index)
  - [Install Lefthook](#doc-install)
- [Installation methods](#installation-methods)
  - [Ruby](#doc-installation-ruby)
  - [NPM package](#doc-installation-node)
  - [Go](#doc-installation-go)
  - [Python](#doc-installation-python)
  - [Swift](#doc-installation-swift)
  - [Homebrew for MacOS and Linux](#doc-installation-homebrew)
  - [Winget for Windows](#doc-installation-winget)
  - [Scoop for Windows](#doc-installation-scoop)
  - [APT packages for Debian/Ubuntu Linux](#doc-installation-deb)
  - [RPM packages for CentOS/Fedora Linux](#doc-installation-rpm)
  - [APK packages for Alpine](#doc-installation-alpine)
  - [AUR for Arch](#doc-installation-arch)
  - [Snap for Linux](#doc-installation-snap)
  - [Devbox](#doc-installation-devbox)
  - [Mise](#doc-installation-mise)
  - [Manual installation with prebuilt executable](#doc-installation-manual)
- [Credits](#credits)
  - [Contributors](#doc-misc-contributors)

## Overview

<a id="doc-index"></a>

### What is Lefthook?

Source: [`docs/index.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/index.md).

**Lefthook** is a Git hooks manager. It is

- Fast
- Powerful
- Simple

<a id="doc-index--how-does-lefthook-work"></a>

#### How does lefthook work?

You

- Create [`lefthook.yml`](configuration.md#doc-configuration) configuration file
- Run `lefthook install`

Lefthook installs the configured hooks into `.git/hooks/`. Hook is a simple script that calls `lefthook run {hook-name}` when executed.

<a id="doc-index--how-to-install-lefthook"></a>

#### How to install lefthook?

The most common way is to use the package manager of your project, e.g. [gem](getting-started.md#doc-installation-ruby) or [npm package](getting-started.md#doc-installation-node).

You can also install lefthook via [Homebrew](getting-started.md#doc-installation-homebrew), [`winget`](getting-started.md#doc-installation-winget), [`yum`](getting-started.md#doc-installation-rpm), [`apt`](getting-started.md#doc-installation-deb), [`apk`](getting-started.md#doc-installation-alpine), [`scoop`](getting-started.md#doc-installation-scoop)

<a id="doc-index--example-configuration"></a>

#### Example configuration

Run linters on `pre-commit` hook.

<!-- prettier-ignore -->
```yml
# lefthook.yml

pre-commit:
  parallel: true
  jobs:
    - run: yarn run stylelint --fix '{staged_files}'
      glob: "*.css"
      stage_fixed: true

    - run: yarn run eslint --fix '{staged_files}'
      glob:
        - "*.ts"
        - "*.js"
        - "*.tsx"
        - "*.jsx"
      stage_fixed: true
```

---

**Lefthook** is built by **[Evil Martians](https://evilmartians.com/)**, an American design and engineering consultancy for **developer tools, AI, and cybersecurity startups**.

<a id="doc-install"></a>

### Install Lefthook

Source: [`docs/install.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/install.md).

Lefthook distributes as a standalone, no-deps binary. There are multiple ways to install lefthook but the most common is via package manager for your programming language (see [Installation methods](#installation-methods)).

You can also download just the [binary](https://github.com/evilmartians/lefthook/releases/latest) for your OS and architecture and put it somewhere in your `$PATH` and update it with

<!-- prettier-ignore -->
```
lefthook self-update
```

## Installation methods

<a id="doc-installation-ruby"></a>

### Ruby

Source: [`docs/installation/ruby.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/installation/ruby.md).

<!-- prettier-ignore -->
```ruby
# Gemfile

group :development do
  gem "lefthook", require: false
end
```

Or globally

<!-- prettier-ignore -->
```bash
gem install lefthook
```

**Troubleshooting**

If you see the error `lefthook: command not found` you need to check your $PATH. Also try to restart your terminal.

<a id="doc-installation-node"></a>

### NPM package

Source: [`docs/installation/node.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/installation/node.md).

<!-- prettier-ignore -->
```bash
npm install --save-dev lefthook
```

<!-- prettier-ignore -->
```bash
yarn add --dev lefthook
```

<!-- prettier-ignore -->
```bash
pnpm add -D lefthook
```

> **Note**
>
> If you use `pnpm` package manager make sure to update `pnpm-workspace.yaml`s `onlyBuiltDependencies` with `lefthook` and add `lefthook` to `pnpm.onlyBuiltDependencies` in your root `package.json`, otherwise the `postinstall` script of the `lefthook` package won't be executed and hooks won't be installed.

<a id="doc-installation-node--choose-right-package"></a>

#### Choose right package

Lefthook supports three NPM packages with different ways to deliver the executables

1.  [lefthook](https://www.npmjs.com/package/lefthook) installs one executable for your system

    <!-- prettier-ignore -->
    ```bash
    npm install --save-dev lefthook
    ```

1.  **legacy**[^doc-installation-node-1] [@evilmartians/lefthook](https://www.npmjs.com/package/@evilmartians/lefthook) installs executables for all OS

    <!-- prettier-ignore -->
    ```bash
    npm install --save-dev @evilmartians/lefthook
    ```

1.  **legacy**[^doc-installation-node-1] [@evilmartians/lefthook-installer](https://www.npmjs.com/package/@evilmartians/lefthook-installer) fetches the right executable on installation

    <!-- prettier-ignore -->
    ```bash
    npm install --save-dev @evilmartians/lefthook-installer
    ```

[^doc-installation-node-1]: Legacy distributions are still maintained but they will be shut down in the future.

<a id="doc-installation-go"></a>

### Go

Source: [`docs/installation/go.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/installation/go.md).

The minimum Go version required is 1.26 and you can install

- as global package

<!-- prettier-ignore -->
```bash
go install github.com/evilmartians/lefthook/v2@v2.1.14
```

- or as a go tool in your project

<!-- prettier-ignore -->
```bash
go get -tool github.com/evilmartians/lefthook/v2
```

<a id="doc-installation-python"></a>

### Python

Source: [`docs/installation/python.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/installation/python.md).

<!-- prettier-ignore -->
```sh
python -m pip install --user lefthook
```

<!-- prettier-ignore -->
```sh
uv add --dev lefthook
```

<!-- prettier-ignore -->
```sh
pipx install lefthook
```

<a id="doc-installation-swift"></a>

### Swift

Source: [`docs/installation/swift.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/installation/swift.md).

You can find the Swift wrapper plugin [here](https://github.com/csjones/lefthook-plugin).

Utilize lefthook in your Swift project using Swift Package Manager:

<!-- prettier-ignore -->
```swift
.package(url: "https://github.com/csjones/lefthook-plugin.git", exact: "2.1.14"),
```

Or, with [mint](https://github.com/yonaskolb/Mint):

<!-- prettier-ignore -->
```bash
mint run csjones/lefthook-plugin
```

<a id="doc-installation-homebrew"></a>

### Homebrew for MacOS and Linux

Source: [`docs/installation/homebrew.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/installation/homebrew.md).

<!-- prettier-ignore -->
```bash
brew install lefthook
```

<a id="doc-installation-winget"></a>

### Winget for Windows

Source: [`docs/installation/winget.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/installation/winget.md).

<!-- prettier-ignore -->
```sh
winget install evilmartians.lefthook
```

<a id="doc-installation-scoop"></a>

### Scoop for Windows

Source: [`docs/installation/scoop.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/installation/scoop.md).

<!-- prettier-ignore -->
```sh
scoop install lefthook
```

<a id="doc-installation-deb"></a>

### APT packages for Debian/Ubuntu Linux

Source: [`docs/installation/deb.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/installation/deb.md).

<!-- prettier-ignore -->
```sh
curl -1sLf 'https://dl.cloudsmith.io/public/evilmartians/lefthook/setup.deb.sh' | sudo -E bash
sudo apt install lefthook
```

See all instructions: https://cloudsmith.io/~evilmartians/repos/lefthook/setup/#formats-deb

[![Hosted By: Cloudsmith](https://img.shields.io/badge/OSS%20hosting%20by-cloudsmith-blue?logo=cloudsmith&style=flat-square)](https://cloudsmith.com "Debian package repository hosting is graciously provided by Cloudsmith")

<a id="doc-installation-rpm"></a>

### RPM packages for CentOS/Fedora Linux

Source: [`docs/installation/rpm.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/installation/rpm.md).

<!-- prettier-ignore -->
```sh
curl -1sLf 'https://dl.cloudsmith.io/public/evilmartians/lefthook/setup.rpm.sh' | sudo -E bash
sudo yum install lefthook
```

See all instructions: https://cloudsmith.io/~evilmartians/repos/lefthook/setup/#repository-setup-yum

[![Hosted By: Cloudsmith](https://img.shields.io/badge/OSS%20hosting%20by-cloudsmith-blue?logo=cloudsmith&style=flat-square)](https://cloudsmith.com "RPM package repository hosting is graciously provided by Cloudsmith")

<a id="doc-installation-alpine"></a>

### APK packages for Alpine

Source: [`docs/installation/alpine.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/installation/alpine.md).

<!-- prettier-ignore -->
```sh
sudo apk add --no-cache bash curl
curl -1sLf 'https://dl.cloudsmith.io/public/evilmartians/lefthook/setup.alpine.sh' | sudo -E bash
sudo apk add lefthook
```

See all instructions: https://cloudsmith.io/~evilmartians/repos/lefthook/setup/#formats-alpine

[![Hosted By: Cloudsmith](https://img.shields.io/badge/OSS%20hosting%20by-cloudsmith-blue?logo=cloudsmith&style=flat-square)](https://cloudsmith.com "RPM package repository hosting is graciously provided by Cloudsmith")

<a id="doc-installation-arch"></a>

### AUR for Arch

Source: [`docs/installation/arch.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/installation/arch.md).

- Official [AUR package](https://aur.archlinux.org/packages/lefthook) (compiles from sources)
- Community [AUR package](https://aur.archlinux.org/packages/lefthook-bin) (delivers pre-compiled binaries)

<!-- prettier-ignore -->
```sh
# To compile from sources
yay -S lefthook

# To install only executable
yay -S lefthook-bin
```

<a id="doc-installation-snap"></a>

### Snap for Linux

Source: [`docs/installation/snap.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/installation/snap.md).

<!-- prettier-ignore -->
```sh
snap install --classic lefthook
```

<a id="doc-installation-devbox"></a>

### Devbox

Source: [`docs/installation/devbox.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/installation/devbox.md).

Add lefthook in the devbox environment.
lefthook already exists in the [Nix package](https://search.nixos.org/packages?channel=25.05&show=lefthook&from=0&size=50&sort=relevance&type=packages&query=lefthook)

<!-- prettier-ignore -->
```bash
devbox add lefthook@latest
```

> **Note**
>
> The devbox plugin for lefthook is maintained by the community. While we appreciate their contribution, the lefthook team cannot provide direct support for devbox-specific installation issues.

<a id="doc-installation-mise"></a>

### Mise

Source: [`docs/installation/mise.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/installation/mise.md).

> See [https://github.com/jdx/mise](https://github.com/jdx/mise)

<!-- prettier-ignore -->
```bash
mise use lefthook@latest
```

> **Note**
>
> The mise plugin for lefthook is maintained by the community. While we appreciate their contribution, the lefthook team cannot provide direct support for mise-specific installation issues.

<a id="doc-installation-manual"></a>

### Manual installation with prebuilt executable

Source: [`docs/installation/manual.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/installation/manual.md).

Download binaries from [latest release](https://github.com/evilmartians/lefthook/releases/latest) and install manually.

## Credits

<a id="doc-misc-contributors"></a>

### Contributors

Source: [`docs/misc/contributors.md`](https://github.com/evilmartians/lefthook/blob/1e23553eec2392753c5420d348e63a63f517cd45/docs/misc/contributors.md).

- [Arkweid](https://github.com/Arkweid)
- [Envek](https://github.com/Envek)
- [mrexox](https://github.com/mrexox)
- [skryukov](https://github.com/skryukov)
- [scop](https://github.com/scop)
- [hyperupcall](https://github.com/hyperupcall)
- [MartijnCuppens](https://github.com/MartijnCuppens)
- [palkan](https://github.com/palkan)
- [markovichecha](https://github.com/markovichecha)
- [technicalpickles](https://github.com/technicalpickles)
- [aminya](https://github.com/aminya)
- [prog-supdex](https://github.com/prog-supdex)
- [HellSquirrel](https://github.com/HellSquirrel)
- [Evilweed](https://github.com/Evilweed)
- [PikachuEXE](https://github.com/PikachuEXE)
- [jsmestad](https://github.com/jsmestad)
- [DmitryTsepelev](https://github.com/DmitryTsepelev)
- [pmirecki](https://github.com/pmirecki)
- [0legovich](https://github.com/0legovich)
- [zachahn](https://github.com/zachahn)
- [sitiom](https://github.com/sitiom)
- [spearmootz](https://github.com/spearmootz)
- [pwinckles](https://github.com/pwinckles)
- [pablobirukov](https://github.com/pablobirukov)
- [nihalgonsalves](https://github.com/nihalgonsalves)
- [nesk](https://github.com/nesk)
- [jaydorsey](https://github.com/jaydorsey)
- [fantua](https://github.com/fantua)
- [orsinium](https://github.com/orsinium)
- [fabn](https://github.com/fabn)

If you feel you’re missing from this list, feel free to add yourself in a PR.

<!-- curl https://api.github.com/repos/evilmartians/lefthook/contributors | jq -r ".[] | \"- [\" + .login + \"](\" + .html_url + \")\"" -->
