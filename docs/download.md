# Get Cadrumo

This page covers the ways to get Cadrumo onto your machine: what is available
today, how to install it, and how to confirm the install works before you
prepare your first declaration. Cadrumo runs on Windows, macOS, and Linux.

```{important}
Cadrumo is pre-alpha. The one supported way to get it today is the source
checkout below. Do not install Cadrumo from PyPI, a public plugin marketplace,
Scoop, Homebrew, or a Desktop extension bundle until the project announces
those channels as available: packages under the same name on public registries
are not this project's tested releases. Release announcements land in
[Updates](updates.md).
```

## What you need

- Python 3.13 or newer.
- [Git](https://git-scm.com/downloads) and [uv](https://docs.astral.sh/uv/getting-started/installation/),
  each installed per its official guide for your operating system.
- Around 200 MB of free disk space.

No taxpayer data, AEAT credentials, or online account is needed to install.
Cadrumo stores everything locally and encrypted; nothing about your taxes
leaves your machine during installation.

## Install from the source checkout

The install is identical on every operating system once Git and uv are
present. Run, in a terminal:

```bash
git clone https://github.com/nevenincs/cadrumo.git
cd cadrumo
uv sync
```

`uv sync` creates an isolated environment and installs the `aeat` command
into it with every core dependency pinned. Nothing is installed globally and
nothing outside the checkout directory is modified: removing the directory
removes Cadrumo.

## Confirm the install

Run the version check from the checkout:

```bash
uv run aeat --version
```

A version number means the install worked. Then run the full workstation
check and add any optional extras you want (Google export, the live AEAT
browser, OFX/QFX import, the agent surface) by following
[Install Cadrumo](workstation-setup.md), which covers the dependency report,
platform checks, and per-extra install commands.

## Distribution channels

Native packages are built and tested per release for the channels below.
They are in final pre-publication verification: none is published yet, and
this page will show the exact install command for each channel the moment
its release is announced.

```{list-table}
:header-rows: 1
:widths: 22 30 48

* - Platform
  - Channel
  - Status
* - Windows (x86-64)
  - Scoop package
  - In verification, not yet published
* - macOS (Apple silicon and Intel)
  - Homebrew formula
  - In verification, not yet published
* - Linux (x86-64 and arm64)
  - Homebrew formula
  - In verification, not yet published
* - Any platform with Python
  - PyPI package (pip, uvx)
  - In verification, not yet published
* - Claude Code, Claude Desktop, Claude Cowork
  - Plugin and Desktop extension bundle
  - In verification, not yet published
```

Every published artifact will carry the exact bytes that passed the release
cohort's install-and-run evidence on its platform; a channel is only listed
as available here once that evidence exists for the published release.

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
