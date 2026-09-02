# Connect an agent (MCP)

Use this when you want an AI assistant, such as Claude, to operate Cadrumo with
you. The assistant reads your records, asks the engine to run calculations, and
explains results in plain language. Every figure still comes from the
deterministic engine, and nothing is ever submitted to the Agencia Estatal de
Administración Tributaria (AEAT): the agent surface exposes the same local,
gated commands the CLI does.

## What the agent connection is

Installing Cadrumo installs two commands: `aeat`, the application, and
`cadrumo-mcp`, an MCP (Model Context Protocol) server that exposes it. MCP is an
open standard that lets assistants call tools. Any MCP-capable client can
connect; Claude is one such client.

The server exposes the CLI's read and prepare operations as tools, plus grounded
search over the bundled BOE and AEAT legal corpus. It refuses live submission by
construction, exactly like the CLI.

## Check the server is installed

```bash
cadrumo-mcp --help
```

If the command is not found, install Cadrumo first — see
[Get Cadrumo](../download.md).

## Register the server

Register `cadrumo-mcp` as a stdio server. In clients that accept a JSON server
definition:

```json
{
  "mcpServers": {
    "cadrumo": {
      "command": "cadrumo-mcp"
    }
  }
}
```

That is the whole configuration. The command is on your `PATH` after
installation, and it finds your profile the same way `aeat` does, so it needs
no working directory and no path of its own.

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
