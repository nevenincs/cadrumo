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

## Set up the browser and the local AI

Two optional extras use a component that Cadrumo sets up on this computer.
The `browser` extra drives a Chromium build for live AEAT reads. On-host
document reading uses the local AI: its program and the model you choose for
each local reader role (vision transcription, text extraction, tabular mapping,
and supply-nature proposal). Cadrumo pins the exact version of the browser and
of the local AI program, and checks each of their downloads against its pinned
size and checksum.

See where you stand first. `aeat config provision status` reads only what this
computer already has, so it downloads nothing and works offline. Each row that
is not ready says how to fix it.

### Set up the browser

To set up the browser, run `aeat config provision setup`. The command first
checks that it can reach the download servers. It then prints its plan: what it
downloads, how large each part is, which server it comes from, and where it is
stored. It asks before it downloads anything. `--yes` approves exactly the plan
the command prints, without asking. Without `--yes` and without a terminal to
answer on, nothing is downloaded and the command says it needs your approval.
A browser that is already set up is left as it is.

To set up the browser alone:

```{cli-sequence} provision-browser
```

To delete the browser from this computer, run
`aeat config provision remove browser`. The command asks first, and `--yes`
confirms without asking. You can set it up again at any time.

Offline, `status` still answers and a browser that is already set up keeps
working. `setup` refuses before it downloads anything, and says whether the
computer is offline, a server cannot be reached, or the network blocked the
download.

### Set up the local AI in the desktop app

Only the Cadrumo desktop app sets up the local AI. The `aeat` command line, the
terminal interface and an AI assistant connected through MCP cannot install,
remove or update it, and cannot choose its models. When the local AI is not
ready, they point you to the desktop app.

In the desktop app, choose a model for each reader role. Cadrumo names no model
and sets no default: the models on offer come from the Cadrumo agent's
catalogue, which shows each model's size, context length, licence, whether it
reads images, and whether it runs on this computer. The desktop app then
downloads the local AI program (Ollama) as a pinned archive from its publisher,
and downloads the models you chose for the local roles. It shows its plan,
with the size of each download, before it downloads anything. Cadrumo keeps the
program in its own storage, so it needs no package manager, no administrator
rights, and no separate installer on Windows, macOS, or Linux.

A copy of the local AI program (Ollama) that you installed yourself is
detected and left alone. Cadrumo never starts, stops, or changes it, and its
own copy listens on a different local address.

The local AI runs in the background under the Cadrumo manager, which starts
when you sign in to your computer or open the Cadrumo app. The manager starts
the local AI once it is set up, starts it again if it stops unexpectedly, and
stops it when the manager ends. No command starts it by hand. Where no manager
runs, as in a source checkout, the local AI reads as not running, and document
reading refuses until it runs.

Every model request goes through the Cadrumo agent service to the model chosen
for its role. LLM classification uses only a model that runs on this computer.
See
[Classify transactions with an LLM](how-to/classify-with-llm.md#set-up-the-local-reader).

### Check every component

`aeat config provision verify` checks every component fully: it reaches the
download servers, opens the browser, and asks each chosen local model for a
one-word answer. `--item browser` or `--item local_ai` checks one component.
The check downloads nothing and exits with status 2 unless each component it
checks is usable.

These commands work with or without a signed-in profile. A Cadrumo build
without its native components, such as a source checkout that has not built
them, reports every component as not included in that version.

Run `aeat config check` again after each change to confirm the gap is closed.

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
