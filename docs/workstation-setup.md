# Install Cadrumo

This page covers installation only: get the package, install the `aeat`
command, add the optional extras you want, and — if you use an AI assistant —
install the agent surface. Configuration and first use start in the
[quickstart](how-to/quickstart.md) once the install checks pass.

Cadrumo works without any optional service. Google export, on-host LLM vision,
cloud LLM upload, and the agent surface are all opt-in. The core filing
workflow runs with none of them.

## Before you start

You need:

- Python 3.13 or newer, with `pip` available.
- Around 200 MB of free disk space.

## Install the CLI

Download the current Cadrumo package from the
[releases page](https://github.com/nevenincs/cadrumo/releases/latest). Each
release lists its downloadable files and release notes; record the version you
install, as [Updates and downloads](updates.md) recommends.

Install the downloaded wheel file. The filename carries the version you
downloaded — the current release is `0.2.1`:

```bash
pip install ./cadrumo-0.2.1-py3-none-any.whl
```

## Confirm the install

Confirm the command is on your path:

```bash
aeat --version
```

Then ask `aeat` what is installed and what is missing:

```bash
aeat config check
```

The report lists each external dependency, whether it is available, and the
exact command to fix any gap. It exits with an error when a capability you
turned on has a missing dependency.

Run the check with machine-readable output when you script the setup.
`--format json` is a global flag, so it goes before the command:

```bash
aeat --format json config check
```

## Install optional extras

The core install is lean. Google export, the live AEAT browser, the
Anthropic-API provider, OFX/QFX bank-statement import, and the agent surface
are optional package extras. Name the extras you need when you install the
wheel:

```bash
pip install "./cadrumo-0.2.1-py3-none-any.whl[google,browser]"
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
with that provider's flow — see
[Classify transactions with an LLM](how-to/classify-with-llm.md#set-up-a-provider).

Run `aeat config check` again after each change to confirm the gap is closed.

## Install the AI-assistant surface (MCP)

Cadrumo ships an MCP (Model Context Protocol) server, `cadrumo-mcp`, so an AI
assistant can operate the same local, gated commands the CLI exposes. There
are three ways to install it — pick the one that matches your client.
[Connect an agent](how-to/connect-an-agent.md) walks through each in full and
explains what the agent can and cannot do.

### Claude plugin (recommended for Claude Code, Claude Desktop, and Cowork)

The plugin bundles the server configuration together with the rules, skills,
and scoped agent personas that keep the assistant inside the safety boundary.
It launches the server itself through `uvx`, so it needs
[uv](https://docs.astral.sh/uv/) on your `PATH` — and nothing else installed
beforehand. Add the marketplace once, then install the plugin:

```text
/plugin marketplace add nevenincs/neve-marketplace
/plugin install cadrumo@neve
```

### Claude Desktop extension bundle (`.mcpb`)

Classic Claude Desktop can also load Cadrumo as a Desktop Extension bundle.
The bundle points at the `cadrumo-mcp` command on your machine, so install the
`agent` extra first:

```bash
pip install "./cadrumo-0.2.1-py3-none-any.whl[agent]"
```

The bundle is built from the source tree:

```bash
python packaging/mcpb/build.py
```

The build writes `dist/cadrumo.mcpb`; open it with Claude Desktop to install.

### Any other MCP client

Install the `agent` extra as above, confirm the server script is on your
path:

```bash
cadrumo-mcp --help
```

then register `cadrumo-mcp` as a stdio server in your client's MCP
configuration — the exact JSON is in
[Connect an agent](how-to/connect-an-agent.md#connect-any-other-mcp-client).

## Next steps

- [Quickstart](how-to/quickstart.md) — from an empty profile to an exported
  modelo file.
- [Set up a profile](how-to/profile-setup.md) — including the per-profile
  service capabilities (Google export, LLM vision, cloud evidence upload).
- [Connect an agent](how-to/connect-an-agent.md)
- [Troubleshooting](how-to/troubleshooting.md)
