# Connect an agent (MCP)

Use this when you want an AI assistant, such as Claude, to operate Cadrumo with
you. The assistant reads your records, asks the engine to run calculations, and
explains results in plain language. Every figure still comes from the
deterministic engine, and nothing is ever submitted to the Agencia Estatal de
Administración Tributaria (AEAT): the agent surface exposes the same local,
gated commands the CLI does.

## What the agent connection is

Cadrumo ships an MCP (Model Context Protocol) server, `cadrumo-mcp`, alongside
the `aeat` command. MCP is an open standard that lets assistants call tools.
Any MCP-capable client can connect; Claude is one such client.

The server exposes the CLI's read and prepare operations as tools, plus
grounded search over the bundled BOE and AEAT legal corpus. It refuses live
submission by construction, exactly like the CLI.

There are three ways to connect, covered in order below: the Claude plugin,
the Claude Desktop extension bundle, and a plain MCP server registration for
any other client. Pick one. They all run the same server.

## Connect Claude through the plugin (recommended)

For Claude Code, Claude Desktop, or Cowork, install the published plugin. It
bundles the MCP server configuration together with the rules, skills, and
scoped agent personas that keep the assistant inside the safety boundary.

The plugin launches the server itself through `uvx`, so the only prerequisite
is [uv](https://docs.astral.sh/uv/) on your `PATH`. You do not need to
install the `agent` extra first. Add the marketplace once, then install the
plugin:

```text
/plugin marketplace add nevenincs/neve-marketplace
/plugin install cadrumo@neve
```

The plugin's settings expose two options: a **persona** that scopes the tool
surface to one role (leave blank for the full surface), and a **tool surface**
choice between the default orientation core and advertising every verb up
front.

## Connect Claude Desktop with the extension bundle

Claude Desktop also loads Cadrumo as a Desktop Extension bundle (`.mcpb`).
Download `cadrumo.mcpb` from the
[releases page](https://github.com/nevenincs/cadrumo/releases/latest) and open
it with Claude Desktop.

The bundle installs the Cadrumo release it was built for. On first launch it
runs the server through `uvx`, which fetches the pinned `cadrumo[agent]`
package from PyPI. The only prerequisite is
[uv](https://docs.astral.sh/uv/) on your `PATH`; no separate `pip install` is
needed. The bundle is unsigned, so Claude Desktop shows its standard
unsigned-extension prompt when you install it.

Its settings expose the same two options as the plugin: the persona and the
tool surface.

## Connect any other MCP client

Install the `agent` extra from PyPI and confirm the server script is on your
path. Without the extra, `cadrumo-mcp` refuses with an install hint instead
of running:

```bash
pip install "cadrumo[agent]"
cadrumo-mcp --help
```

Then register `cadrumo-mcp` as a stdio server in your client's MCP
configuration:

```json
{
  "mcpServers": {
    "aeat": {
      "command": "cadrumo-mcp",
      "args": []
    }
  }
}
```

## Before the first agent session

The server uses the same local encrypted store and the same active profile
as the CLI. A server cannot answer a passphrase prompt, so configure the
passphrase for unattended runs first - see
[Run without a passphrase prompt](protect-data-access.md#run-without-a-passphrase-prompt).

## What the agent can and cannot do

The agent can import and classify records, run calculations, verify drafts, and
prepare exports, because those are local operations. It cannot file, notify, or
submit anything to AEAT, and it cannot invent a figure: calculations always run
inside the deterministic engine, and every value keeps its legal references.
You review and file yourself, exactly as in the
[Quickstart](quickstart.md) and the
[filing guide](file-at-aeat.md).
