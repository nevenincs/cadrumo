# Install Cadrumo

This page covers installation only: install the `aeat` command, confirm it
runs, and add the optional extras you want. If you do not have Cadrumo on your
machine yet, start at [Get Cadrumo](download.md) for the install channels.
Configuration and first use start in the [quickstart](how-to/quickstart.md)
once the install checks pass.

Cadrumo works without any optional service. Google export, reading scanned or
image documents with a model you select, and cloud LLM upload are all optional,
and so is connecting an AI assistant. The core filing workflow runs with none of
them.

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

Version and capability checks need no taxpayer profile. Create a profile with
`aeat config profile create` when you are ready to use Cadrumo. See
[Set up a profile](how-to/profile-setup.md).

Confirm the command is on your path and the capability posture is readable.
Then run the workstation check on your own machine. Its dependency and
platform rows intentionally reflect that workstation, including tools on
your path and operating-system settings. Use the machine-readable form for
scripted setup checks (`--format json` is a global flag, so it goes before the
command):

```{cli-sequence} install-confirm
```

## Install optional extras

The core install is lean. Each optional extra adds one capability:

- `google` - Google Drive and Sheets export.
- `browser` - live AEAT reads through browser automation.
- `ofx` - OFX and QFX bank-statement import.
- `llm` - on-host document reading through the local AI.
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

Run `aeat config check` after each change to confirm the gap is closed.

## Connect an AI assistant

Cadrumo installs `cadrumo-mcp` alongside `aeat`. The server connects an agent
to registered operations through the local runtime, either under your own
Cadrumo sign-in or under an enrolled key for one profile. Run
`cadrumo-mcp --help` to confirm it is on your path. In a source checkout, check
the installed entrypoint with:

```bash
uv sync
uv run --no-sync cadrumo-mcp --help
```

[Connect an agent](how-to/connect-an-agent.md) shows both ways to connect and
the grant request flow.

## Next steps

- [Quickstart](how-to/quickstart.md) - from an empty profile to an exported
  modelo file.
- [Set up a profile](how-to/profile-setup.md) - including the per-profile
  service capabilities (Google export, LLM vision, cloud evidence upload).
- [Connect an agent](how-to/connect-an-agent.md)
- [Troubleshooting](how-to/troubleshooting.md)
