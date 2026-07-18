# Get Cadrumo

This page covers how to install the current Cadrumo beta: the supported
install paths, what each one gives you, and how to confirm the install before
you prepare your first declaration. Cadrumo runs on Windows, macOS, and Linux.

```{note}
Cadrumo is in beta. Every release ships installable packages for each
supported channel, and every package is install-tested on its platform before
the release is cut. The beta is distributed through the project's GitHub
repository; public registry listings open with the public launch.
```

## What you need

- Python 3.13 or newer.
- [Git](https://git-scm.com/downloads) and [uv](https://docs.astral.sh/uv/getting-started/installation/),
  each installed per its official guide for your operating system.
- Around 200 MB of free disk space.
- Access to the [project repository](https://github.com/nevenincs/cadrumo)
  as a beta participant.

No taxpayer data, AEAT credentials, or online account is involved in the
install. Cadrumo stores everything locally and encrypted; nothing about your
taxes leaves your machine.

## Install the current beta

Install from the repository checkout. The flow is identical on Windows,
macOS, and Linux:

```bash
git clone https://github.com/nevenincs/cadrumo.git
cd cadrumo
uv sync
```

`uv sync` creates an isolated environment and installs the `aeat` command
into it with every dependency pinned to the tested versions. Nothing is
installed globally and nothing outside the checkout directory is modified:
removing the directory removes Cadrumo. To move to a newer beta release
later, run `git pull` followed by `uv sync` in the same directory.

Release artifacts for the current version, including the packaged builds for
every channel below, are attached to the
[latest release](https://github.com/nevenincs/cadrumo/releases/latest).

## Confirm the install

Run the version check from the checkout:

```bash
uv run aeat --version
```

A version number confirms the install. Then run the full workstation check
and add the optional extras you want (Google export, the live AEAT browser,
OFX/QFX import, the agent surface) by following
[Install Cadrumo](workstation-setup.md), which covers the dependency report,
platform checks, and per-extra install commands. To let an AI assistant such
as Claude drive Cadrumo, continue with
[Connect an agent (MCP)](how-to/connect-an-agent.md).

## Install channels

Each release builds and install-tests a native package per channel. Beta
participants get every artifact from the release page; the registry listing
for each channel opens with the public launch, and this page carries each
channel's install command from that day.

```{list-table}
:header-rows: 1
:widths: 24 32 44

* - Platform
  - Channel
  - How you get the current beta
* - Windows (x86-64)
  - Scoop package
  - Release page artifact; Scoop bucket at public launch
* - macOS (Apple silicon and Intel)
  - Homebrew formula
  - Release page artifact; Homebrew tap at public launch
* - Linux (x86-64 and arm64)
  - Homebrew formula
  - Release page artifact; Homebrew tap at public launch
* - Any platform with Python
  - Python package
  - Repository checkout today; PyPI at public launch
* - Claude Code, Claude Desktop, Claude Cowork
  - Plugin and Desktop extension bundle
  - Release page artifact; marketplace listing at public launch
```

Every published artifact carries the exact bytes that passed its platform's
install-and-run checks for that release, and each release's notes in
[Updates](updates.md) name what changed.

## After you install

::::{grid} 1 2 2 2
:gutter: 3
:class-container: cadrumo-route-grid

:::{grid-item-card} Quickstart
:link: how-to/quickstart
:link-type: doc
:class-card: cadrumo-route-card

Take the shortest path from an empty profile to an exported modelo file.
:::

:::{grid-item-card} Connect an agent (MCP)
:link: how-to/connect-an-agent
:link-type: doc
:class-card: cadrumo-route-card

Let an AI assistant such as Claude drive Cadrumo with you, on your machine.
:::
::::
