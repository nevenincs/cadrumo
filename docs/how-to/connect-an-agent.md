# Connect an agent (MCP)

The installed `cadrumo-mcp` command connects an MCP client to Cadrumo's local
runtime. Each connection is bound to one profile ID. The client can discover and
run only operations allowed by its current grant and session; a later switch of
the human active profile does not retarget it.

Before authorizing an agent or managing its access, set up the intended profile
using [Set up a profile](profile-setup.md) and establish a human password-authorized
session for it. Checking installation does not require profile authentication.

## Check the installation

```bash
cadrumo-mcp --help
```

If `cadrumo-mcp` is unavailable, install Cadrumo first; see
[Get Cadrumo](../download.md). The command and the `aeat` CLI ship in the same
Cadrumo distribution. The adapter connects to an already running local runtime.
An unavailable or untrusted endpoint returns a connection refusal; connecting
does not install or start a service.

## Register one profile-bound server

Find the intended profile ID in Cadrumo. CLI output hides profile IDs by default;
set `CADRUMO_CLI_REVEAL_IDENTIFIERS=1` for the command's process and run
the following profile-view command to display it. This option reveals opaque
profile and bucket IDs; credentials remain hidden.

```{cli-sequence} connect-an-agent-profile-view
```

Register `cadrumo-mcp` as a stdio server in your MCP client. For clients that
accept a JSON server definition:

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

If the configured reference cannot authenticate, the MCP connection stays open.
Use `status` to inspect the refusal; private operations remain unavailable.
Restore access to the protected store or obtain an approved replacement reference,
then call `authenticate` explicitly. Public `authority` queries remain available.

Before authentication, `corpus_search` searches the bundled BOE/AEAT corpus
and approved tax terminology. Supply `query` and optionally `limit` (1–50).
An exact citation ID returns its published verbatim text; other queries return
ranked offline evidence and terminology matches. The response identifies the
publication generation used for citation lookup. This public search reads no
profile data.

## Authorize the connection

On a first connection, ask the agent to use `status`, then
`authorization_prepare` and `authorization_request` for the operations, periods
and disclosures it needs. Review and approve that request in Cadrumo's CLI or
TUI. The agent uses `authorization_poll` to receive the protected reference and
`authenticate` to start an independently tracked session. A password or stored
credential alone is not an authenticated agent session.

After admission, `search` ranks permitted operations by the query, using their
current contracts and request vocabulary; omit the query to list them.
`describe` shows a
registered operation's input contract, `execute` submits it, and `observe`
tracks its result. The separate `authority` tool reads published tax authority
data. Operation grants, session locks, profile suspension, provider checks and
human review still apply. Retain operation IDs and reconcile uncertain effects
after a disconnect instead of submitting the same effect blindly.

Read a settled operation's approved projection with `result`. For a large result,
use `result_page` with the same result request and an initial page offset of zero.
Continue at the returned byte boundary, supplying the document digest from the
first page as `expected_digest`. Assemble and verify the complete document before
using it. Each page requires current authorization; a lock or revocation can stop
the remaining pages. An incomplete document is not a complete result.

To rotate or narrow an existing grant, reconnect with its protected credential
reference and prepare a new authorization request. Human approval is required
for the change. Revoking the grant prevents future admission under that key.

Discover the currently supported operations with `search`; a CLI command's
availability alone does not make it available through MCP. Calculations use
Cadrumo's deterministic engine and published tax authority. Connecting an agent
does not authorize submission to AEAT. Review the prepared filing yourself as
described in the [filing guide](file-at-aeat.md).

## Review and manage access as the profile owner

Use a human password-authorized session for the intended profile, as described
in [Set up a profile](profile-setup.md). The agent's API-key session cannot approve
its own request or administer other clients. Check the profile ID in each result.

List pending requests and inspect the exact request before deciding:

```{cli-sequence} connect-an-agent-request-inspection
```

Replace `REQUEST_UUID` with the returned request ID. Review the client and
destination, operations, actions, disclosures, periods, expiry, unattended access
and OS-lock permission. Copy the current `review_digest` from that inspection.
Approve only those reviewed permissions, or decline the request:

```{cli-sequence} connect-an-agent-request-decision
```

Run one decision command. Approval asks for a fresh profile password through a
hidden terminal prompt; decline does not. For controlled automation, approval and
profile recovery also accept `--secrets-stdin` or `--secrets-fd DESCRIPTOR` using
the command's machine-secret schema. Keep secret values out of command arguments,
environment variables, chat and ordinary output. Inspect the returned receipt:
a recorded decision alone does not prove completed protected delivery. The agent
must finish polling and authenticate with the delivered reference.

The same review procedure applies to rotation, renewal and scope-change requests.
Enrollment and rotation can deliver a new protected reference; renewal and scope
changes retain the existing reference.
An explicitly approved unattended grant can remain usable after the human
Cadrumo session ends. It still depends on its validity interval, protected
custody and an eligible OS login context. Continuing during OS lock requires the
grant's explicit OS-lock permission. A current-session lock does not revoke that
independent grant.

Use the inventory's non-secret key or grant ID to revoke access:

```{cli-sequence} connect-an-agent-revocation
```

Check `access_denied` and `cleanup_pending` in text output; in the JSON result,
inspect `receipt.access_denied` and `receipt.cleanup_pending`. Pending physical
credential-store cleanup is distinct from whether access has been denied.

List sessions, then choose the intended lock scope. A current-session lock ends
the caller's session; a selected-session lock ends that session. A profile-wide
lock suspends its automation.

```{cli-sequence} connect-an-agent-session-lock
:verify: Confirm private profile access refuses while the profile-wide lock remains active.
```

To resume, supply the fresh password at the hidden prompt. Add `--grant GRANT_UUID`
for each grant you deliberately reactivate; omitting it restores human access
without reactivating grants.

```{cli-sequence} connect-an-agent-profile-resume
```

Confirm the returned grant IDs, then let agents reconnect and authenticate afresh.
