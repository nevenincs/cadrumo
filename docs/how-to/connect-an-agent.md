# Connect an agent (MCP)

The installed `cadrumo-mcp` command connects an MCP client to Cadrumo's local
runtime. Each connection is bound to one profile ID. The client can discover and
run only operations allowed by its current grant and session; a later switch of
the human active profile does not retarget it.

## Check the installation

```bash
cadrumo-mcp --help
aeat app runtime status
```

If `cadrumo-mcp` is unavailable, install Cadrumo first. The command and the
`aeat` CLI ship in the same Cadrumo distribution. Start or provision the local
runtime using the controls described in [Workstation setup](../workstation-setup.md).

## Register one profile-bound server

Find the intended profile ID in Cadrumo, then register `cadrumo-mcp` as a stdio
server in your MCP client. For clients that accept a JSON server definition:

```json
{
  "mcpServers": {
    "cadrumo": {
      "command": "cadrumo-mcp",
      "args": ["--profile-id", "YOUR-PROFILE-UUID"]
    }
  }
}
```

Use a separate server entry for each profile. The profile ID is required; the
server does not select the human's active profile. Keep credentials out of the
configuration and conversation. An approved protected credential reference can
be supplied with `--credential-reference` for a later connection, while its
grant and the profile remain eligible.

## Authorize the connection

On a first connection, ask the agent to use `status`, then
`authorization_prepare` and `authorization_request` for the operations, periods
and disclosures it needs. Review and approve that request in Cadrumo's CLI or
TUI. The agent uses `authorization_poll` to receive the protected reference and
`authenticate` to start an independently tracked session. A password or stored
credential alone is not an authenticated agent session.

After admission, `search` lists permitted operations, `describe` shows a
registered operation's input contract, `execute` submits it, and `observe`
tracks its result. The separate `authority` tool reads published tax authority
data. Operation grants, session locks, profile suspension, provider checks and
human review still apply. Retain operation IDs and reconcile uncertain effects
after a disconnect instead of submitting the same effect blindly.

To rotate or narrow an existing grant, reconnect with its protected credential
reference and prepare a new authorization request. Human approval is required
for the change. Revoking the grant prevents future admission under that key.
