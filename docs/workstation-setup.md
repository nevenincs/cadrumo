# Install Cadrumo

This page covers installation only: install the `aeat` command, confirm it
runs, and add the optional extras you want. If you do not have Cadrumo on your
machine yet, start at [Get Cadrumo](download.md) for the install channels.
Configuration and first use start in the [quickstart](how-to/quickstart.md)
once the install checks pass.

Cadrumo works without any optional service. Google export, on-host LLM vision,
and cloud LLM upload are all optional, and so is connecting an AI assistant. The
core filing workflow runs with none of them.

## Before you start

You need:

- Python 3.13 or newer.
- Several hundred megabytes of free disk space for Cadrumo and its
  dependencies. The package download alone is about 76 MB.

## Install the CLI

Pick one channel from the table in [Get Cadrumo](download.md#install-channels)
and run the command it lists. A `uv` tool install keeps Cadrumo out of your
global Python environment. Homebrew and Scoop packages are not published yet,
so use a Python package channel on every platform for now.

The Python package installs both the `aeat` command and the `cadrumo-mcp`
server.

If you contribute to Cadrumo, work from a source checkout instead:

```bash
git clone https://github.com/nevenincs/cadrumo.git
cd cadrumo
uv sync
uv run aeat --version
```

## Confirm the install

No taxpayer profile is needed for these checks; you create one with
`aeat config profile create` after installing. See
[Set up a profile](how-to/profile-setup.md).

Confirm the command is on your path and the capability posture is readable.
Then run the workstation check on your own machine. Its dependency and
platform rows intentionally reflect that workstation, including tools on
your path, installed browser assets, and operating-system settings. Use the
machine-readable form for scripted setup checks (`--format json` is a global
flag, so it goes before the command):

```{cli-sequence} install-confirm
```

## Install optional extras

The core install is lean. Each optional extra adds one capability:

- `google` - Google Drive and Sheets export.
- `browser` - live AEAT reads through browser automation.
- `anthropic` - the Anthropic API as a hosted provider for
  `aeat app ledger evidence extract --off-host-provider`, which sends a document
  off your machine only when you acknowledge it for that one read.
- `ofx` - OFX and QFX bank-statement import.
- `llm` - on-host document reading with a local model runtime.
- `pdf` - writing the calculation-summary PDF. Reading and verifying a summary
  needs no extra.
- `all` - every extra in this list.

Name the extras you need when you install: in your channel's install command,
write the package as `cadrumo[google,browser]` instead of `cadrumo`. Extras
install into the same environment as Cadrumo, so use the channel you installed
with. In a source checkout, add extras with `uv sync --extra google --extra browser`.

`aeat config check` reports each extra as `extra:<name>` available or missing.
Install a missing one by repeating your channel's install command with that
extra named.

Two extras need a further provisioning step after the install:

- The `browser` extra drives a Chromium build for live AEAT reads. Download
  the exact build the installed extra launches with:

  ```{cli-sequence} provision-browser
  ```

  It does nothing when that build is already present. With the browser
  channel set to `chromium`, a browser read that finds the build missing
  refuses and names this command.

- On-host invoice reading uses a local model runtime (Ollama) with one model
  for each reader role: vision transcription, text extraction, tabular
  mapping, and supply-nature proposal. Run `aeat config provision status` to
  see where you stand: whether the runtime is installed, whether it answers,
  and which reader models are present.

  To close every gap in one run, use `aeat config provision setup`. It
  installs the runtime, starts it, downloads every role's model, loads the
  models, and verifies them. Steps that are already done report unchanged,
  and the first step that fails stops the run. Setup installs the runtime
  only when you pass `--confirm`.

  To go step by step, run the commands one at a time.
  `aeat config provision install` installs the runtime through `winget` on
  Windows or Homebrew on macOS, and only with `--confirm`; it does nothing
  when the runtime is already installed. On Linux, install Ollama with its
  upstream installer, which needs root. `aeat config provision start` starts
  an installed runtime that is not answering, and does nothing when it
  already answers. `aeat config provision pull` downloads every reader role's
  model, a few GB in total. Narrow it with `--role` to one of
  `vision_transcription`, `text_extraction`, `column_role_mapping`, or
  `supply_nature_proposal`. `aeat config provision verify` confirms each model
  loads and answers.

LLM classification runs only on this local reader; no cloud provider is
involved. See
[Classify transactions with an LLM](how-to/classify-with-llm.md#set-up-the-local-reader).

Run `aeat config check` again after each change to confirm the gap is closed.

## Connect an AI assistant

The Cadrumo package includes `cadrumo-mcp`, the Model Context Protocol (MCP)
server that lets an AI assistant operate the same gated commands as the CLI.
It needs no separate install. Run `cadrumo-mcp --help` to confirm it is on
your path, then follow [Connect an agent](how-to/connect-an-agent.md) to
register it with your assistant. On Windows, install with `pip` or
`uv tool install` to get the command on your path.

## Next steps

- [Quickstart](how-to/quickstart.md) - from an empty profile to an exported
  modelo file.
- [Set up a profile](how-to/profile-setup.md) - including the per-profile
  service capabilities (Google export, LLM vision, cloud evidence upload).
- [Connect an agent](how-to/connect-an-agent.md)
- [Troubleshooting](how-to/troubleshooting.md)
