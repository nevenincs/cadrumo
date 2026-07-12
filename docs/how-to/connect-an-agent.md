# Connect an agent (MCP)

Use this when you want an AI assistant, such as Claude, to operate Cadrumo with
you. The assistant reads your records, asks the engine to run calculations, and
explains results in plain language. Every figure still comes from the
deterministic engine, and nothing is ever submitted to the Agencia Estatal de
Administración Tributaria (AEAT): the agent surface exposes the same local,
gated commands the CLI does.

## What the agent surface is

Cadrumo ships an MCP (Model Context Protocol) server, `aeat-mcp`, alongside the
`aeat` command. MCP is an open standard that lets assistants call tools. Any
MCP-capable client can connect; Claude is one such client.

The server exposes the CLI's read and prepare operations as tools, plus grounded
search over the bundled BOE and AEAT legal corpus. It refuses live submission by
construction, exactly like the CLI.

## 1. Install the agent extra

The MCP runtime is an optional extra of the same `aeat-cli` package:

```bash
pip install "aeat-cli[agent]"
```

Confirm the server script is on your path:

```bash
aeat-mcp --help
```

Without the extra, `aeat-mcp` refuses with an install hint instead of running.

## 2. Connect Claude through the plugin

For Claude Code, Claude Desktop, or Cowork, install the published plugin. Add
the marketplace once, then install the plugin:

```text
/plugin marketplace add nevenincs/neve-marketplace
/plugin install aeat@neve
```

The plugin bundles the MCP server configuration together with the rules,
skills, and scoped agent personas that keep the assistant inside the safety
boundary.

## 3. Connect any other MCP client

Register `aeat-mcp` as a stdio server in your client's MCP configuration:

```json
{
  "mcpServers": {
    "aeat": {
      "command": "aeat-mcp",
      "args": []
    }
  }
}
```

The server uses the same local encrypted store and the same active profile as
the CLI, and prompts for the master-key passphrase the same way. Set
`AEAT_SECRET_PASSPHRASE` in the server's environment to run without a prompt.

## What the agent can and cannot do

The agent can import and classify records, run calculations, verify drafts, and
prepare exports, because those are local operations. It cannot file, notify, or
submit anything to AEAT, and it cannot invent a figure: calculations always run
inside the deterministic engine, and every value keeps its legal references.
You review and file yourself, exactly as in the
[Quickstart](quickstart.md) and the
[filing guide](file-at-aeat.md).
