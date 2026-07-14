# Install Cadrumo

This page covers installation only: get the package, install the `aeat`
command, add the optional extras you want, and (if you use an AI assistant)
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

Cadrumo is published on the Python Package Index (PyPI). Install it with
`pip`:

```bash
pip install cadrumo
```

Record the version you installed, as [Updates and downloads](updates.md)
recommends. The [releases page](https://github.com/nevenincs/cadrumo/releases/latest)
lists each release's notes and downloadable artifacts, including the Claude
Desktop extension bundle covered below.

## Confirm the install

No taxpayer profile is needed for these checks; you create one with
`aeat config profile create` after installing. See
[Set up a profile](how-to/profile-setup.md).

Confirm the command is on your path, then ask `aeat` what is installed and
what is missing. The report lists each external dependency, whether it is
available, and the exact command to fix any gap; it exits with an error when
a capability you turned on has a missing dependency. The last step shows the
machine-readable form for scripted setups (`--format json` is a global flag,
so it goes before the command):

```{cli-sequence} install-confirm
:verify: Confirm the installed command reports its version.
@step Confirm the command is on your path.
@result aeat --version
@expect exit_code == 0
@step Ask what is installed and what is missing.
@static aeat config check
@step Run the same check with machine-readable output for scripted setups.
@static aeat --format json config check
```

## Install optional extras

The core install is lean. Google export, the live AEAT browser, the
Anthropic-API provider, OFX/QFX bank-statement import, and the agent surface
are optional package extras. Name the extras you need when you install:

```bash
pip install "cadrumo[google,browser]"
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

## Install the AI-assistant surface (MCP)

Cadrumo ships an MCP (Model Context Protocol) server, `cadrumo-mcp`, so an AI
assistant can operate the same local, gated commands the CLI exposes,
together with an agent harness: the operator rules, taxpayer-situation
skills, and scoped agent personas that keep the assistant inside the safety
boundary. There are three ways to install the server, plus the harness
workspace for project use. Pick what matches your client.
[Connect an agent](how-to/connect-an-agent.md) walks through each in full and
explains what the agent can and cannot do.

### Before you start: uv and a Claude client

The plugin and the Desktop extension bundle both launch the server through
`uvx`, so install [uv](https://docs.astral.sh/uv/) first:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On Windows:

```pwsh
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

You also need a client. Claude Code, Claude Desktop, and Cowork all work
(see [Claude's own install instructions](https://claude.com/claude-code)),
and any other MCP-capable client connects through the plain server
registration below.

### Claude plugin (recommended for Claude Code, Claude Desktop, and Cowork)

The plugin bundles the MCP server configuration together with the full agent
harness. It launches the server itself through `uvx`, so with uv installed
nothing else is needed beforehand. Add the marketplace once, then install
the plugin:

```text
/plugin marketplace add nevenincs/neve-marketplace
/plugin install cadrumo@neve
```

### Claude Desktop extension bundle (`.mcpb`)

Claude Desktop can load Cadrumo as a Desktop Extension bundle. Download
`cadrumo.mcpb` from the
[releases page](https://github.com/nevenincs/cadrumo/releases/latest) and open
it with Claude Desktop. The bundle installs the Cadrumo release it was built
for: on first launch it runs the server through `uvx`, which fetches the
pinned `cadrumo[agent]` package from PyPI. The only prerequisite is
[uv](https://docs.astral.sh/uv/) on your `PATH`; no separate `pip install` is
needed. The bundle is unsigned, so Claude Desktop shows its standard
unsigned-extension prompt when you install it.

### Any other MCP client

Install the `agent` extra as above, confirm the server script is on your
path:

```bash
cadrumo-mcp --help
```

then register `cadrumo-mcp` as a stdio server in your client's MCP
configuration. The exact JSON is in
[Connect an agent](how-to/connect-an-agent.md#connect-any-other-mcp-client).

### Materialize the agent harness in a project workspace

The plugin carries the harness for you. To place the same harness (rules,
personas, skills, and a `CLAUDE.md`) directly into a project directory
instead, materialize it with the CLI. Use `--layout plugin` to emit the
one-click plugin form of the same content:

```{cli-sequence} install-agent-harness
:verify: Confirm the operator harness materializes as a native Claude workspace.
@step Write the operator harness into a workspace directory.
@result aeat --format json app agent --output ./operator-workspace
@expect exit_code == 0
```

## Next steps

- [Quickstart](how-to/quickstart.md) - from an empty profile to an exported
  modelo file.
- [Set up a profile](how-to/profile-setup.md) - including the per-profile
  service capabilities (Google export, LLM vision, cloud evidence upload).
- [Connect an agent](how-to/connect-an-agent.md)
- [Troubleshooting](how-to/troubleshooting.md)
