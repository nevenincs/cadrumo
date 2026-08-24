# Install Cadrumo

This page covers installation only: get the package, install the `aeat`
command, add the optional extras you want, and (if you use an AI assistant)
install the agent surface. If you do not have Cadrumo on your machine yet,
start at [Get Cadrumo](download.md) for the acquisition paths and their
current availability. Configuration and first use start in the
[quickstart](how-to/quickstart.md) once the install checks pass.

Cadrumo works without any optional service. Google export, on-host LLM vision,
cloud LLM upload, and the agent surface are all opt-in. The core filing
workflow runs with none of them.

## Before you start

You need:

- Python 3.13 or newer, with `pip` available.
- Around 200 MB of free disk space.

## Install the CLI

The beta installs from the project repository:

```bash
git clone https://github.com/nevenincs/cadrumo.git
cd cadrumo
uv sync
uv run aeat --version
```

Registry listings for the packaged channels (PyPI, Scoop, Homebrew, and the
plugin marketplace) open with the public launch; see
[Get Cadrumo](download.md) for each channel's current status.

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
:verify: Confirm the installed command reports its version and its dependency report resolves.
```

## Install optional extras from the checkout

The core install is lean. Google export, the live AEAT browser, the
Anthropic-API provider, OFX/QFX bank-statement import, and the agent surface
are optional package extras. Name the extras you need when you install:

```bash
uv sync --extra google --extra browser
```

The available extras are `google`, `browser`, `anthropic`, `ofx`, `agent`, and
`all`. `aeat config check` lists each extra and prints the exact install
command for any that is missing. A feature whose extra is not installed
refuses with the same hint instead of failing obscurely.

Two extras need a further provisioning step after the pip install:

- The `browser` extra provides the `playwright` command; install the browser
  it drives for live AEAT reads:

  ```bash
  playwright install chromium
  ```

- On-host invoice reading uses a local vision model. Start the Ollama server
  and pull the model named in the `aeat config check` report:

  ```bash
  ollama serve
  ollama pull qwen2.5vl:3b
  ```

For cloud LLM classification, put the provider's own CLI on `PATH` and sign in
with that provider's flow. See
[Classify transactions with an LLM](how-to/classify-with-llm.md#set-up-a-provider).

Run `aeat config check` again after each change to confirm the gap is closed.

## Run the Model Context Protocol (MCP) surface

Cadrumo ships an MCP server, `cadrumo-mcp`, so an AI
assistant can operate the same local, gated commands the CLI exposes,
together with an agent harness: the operator rules, taxpayer-situation
skills, and scoped agent personas that keep the assistant inside the safety
boundary.

In the beta, run the server from the same repository checkout:

```bash
uv sync --extra agent
uv run cadrumo-mcp --help
```

[Connect an agent](how-to/connect-an-agent.md) shows the source-checkout
registration and explains what the agent can and cannot do.

## Next steps

- [Quickstart](how-to/quickstart.md) - from an empty profile to an exported
  modelo file.
- [Set up a profile](how-to/profile-setup.md) - including the per-profile
  service capabilities (Google export, LLM vision, cloud evidence upload).
- [Connect an agent](how-to/connect-an-agent.md)
- [Troubleshooting](how-to/troubleshooting.md)
