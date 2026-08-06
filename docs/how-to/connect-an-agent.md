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

In the beta, connect from the repository checkout below. Every release also
builds the plugin and Desktop extension artifacts; their marketplace and
registry listings open with the public launch (see
[Get Cadrumo](../download.md) for channel status).

## Prepare the source checkout

```bash
git clone https://github.com/nevenincs/cadrumo.git
cd cadrumo
uv sync --extra agent
uv run cadrumo-mcp --help
```

## Register the source server

Register `uv run cadrumo-mcp` as a stdio server and set the checkout as the
working directory. In clients that accept a JSON server definition:

```json
{
  "mcpServers": {
    "cadrumo": {
      "command": "uv",
      "args": ["run", "cadrumo-mcp"],
      "cwd": "/absolute/path/to/cadrumo"
    }
  }
}
```

Replace the example path with the absolute path to your authorized checkout.
Do not replace this with `uvx`, a marketplace install, or a downloaded
extension until public distribution is announced.

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
