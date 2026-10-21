# Connect an agent (MCP)

`cadrumo-mcp` connects an MCP client to the local Cadrumo runtime over standard
input and output. The runtime must already be running. Starting the MCP server
does not install or start Cadrumo, sign in to a profile, or submit a filing to
AEAT.

Before connecting, [set up a profile](profile-setup.md), start Cadrumo, and
select the profile the agent should use. Keep credentials out of the MCP client
configuration and the agent conversation.

## Check the installation

```bash
cadrumo-mcp --help
```

If `cadrumo-mcp` is unavailable, install Cadrumo first; see [Get Cadrumo](../download.md).

## Register the server

Register `cadrumo-mcp` as a stdio server in your MCP client. For a client that
accepts a JSON server definition:

```json
{
  "mcpServers": {
    "cadrumo": {
      "command": "cadrumo-mcp",
      "args": ["--profile-id", "YOUR-PROFILE-UUID", "--surface", "read-only-local"]
    }
  }
}
```

Use a separate server entry for each profile. The profile must be selected in
Cadrumo when the server requests access. `--profile-id` is required when you
configure an enrolled key. The default surface is `full`; choose
`read-only-local` when the connection should only read local data. The runtime
enforces that surface when each operation is submitted.

## Connect with a human session

Without `--credential-reference`, the server starts without a profile session.
When a tool needs profile access, it asks the runtime for attendance from the
currently selected profile. It does not use a stored sign-in receipt or follow
your sign-in automatically.

Review the exact request in Cadrumo before approving it. The request identifies
the client process and the operations, actions, periods, and data categories it
would receive. Approve only a request you started and whose scope you accept.
Until approval, the agent can read its tool list and `status`; other tools are
refused. The approval is tied to that connection and your live human session.
Signing out, locking the profile, changing the selected profile, or ending the
session ends its access.

## Connect with an enrolled key

An enrolled key gives access without a live human session. Create a finite
automation request in the profile's access controls, choosing only the
operations and data categories the agent needs. The terminal command accepts a
complete proposal only through its protected input channel:

```text
cadrumo-runtime config profile automation create --secrets-stdin
```

The request does not issue a key by itself. Inspect the exact request and
approve its current review digest in a separate human-authorized session:

```{cli-sequence} connect-an-agent-request-inspection
```

```{cli-sequence} connect-an-agent-request-decision
```

When protected delivery completes, configure the returned credential reference
with both `--profile-id` and `--credential-reference`. Keep the reference in
protected local configuration. Never put a password, raw key, or secret value
in command arguments, environment variables, chat, or an MCP tool call.

For a keyed server entry, set these arguments in the MCP client configuration:

```json
{
  "command": "cadrumo-mcp",
  "args": [
    "--profile-id",
    "YOUR-PROFILE-UUID",
    "--credential-reference",
    "YOUR-CREDENTIAL-REFERENCE"
  ]
}
```

## Work through the connection

Start with the MCP `status` tool. It reports whether the connection has an
attended session, an enrolled key, or no access, and which surface it serves.
Use `search` to find available operations, `describe` to read an operation's
input contract, `execute` to submit it, and `observe` and `result` to follow it.
The connection can use only the operations allowed by its session, key grant,
and surface.

If an operation has an unknown outcome, do not submit it again. Retain its
operation ID and reconcile the result after reconnecting. Cadrumo calculates
deterministically from its published authority; connecting an agent does not
authorize it to submit a return to AEAT. Review and file returns yourself as
described in the [filing guide](file-at-aeat.md).

## Review and revoke access

Use the profile's human-authorized access controls to inspect requests, grants,
and keys. The terminal command group is
`cadrumo-runtime config profile automation`. To revoke one key, one grant, or
all automation for the profile, use the corresponding `deny` command or the
following reviewed sequence:

```{cli-sequence} connect-an-agent-revocation
```

Locking the current session ends its access. A profile-wide lock also suspends
automation; resuming the profile does not reactivate grants unless you select
them explicitly:

```{cli-sequence} connect-an-agent-session-lock
:verify: Verify profile access is refused while the profile-wide lock remains active.
```

```{cli-sequence} connect-an-agent-profile-resume
```
