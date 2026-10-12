# Connect an agent (MCP)

The installed `cadrumo-mcp` command connects an MCP client to Cadrumo's local
runtime. A connection works in one of two ways: it follows your own Cadrumo
sign-in, or it uses an enrolled key. The client can run only operations allowed
by its current session and, for a key, its grant. It can read which operations
exist, and what each one needs, before anyone signs in and while Cadrumo is not
running. A connection started with a profile ID is not retargeted by a later
switch of the human active profile.

Before connecting an agent or managing its access, set up the intended profile
using [Set up a profile](profile-setup.md) and sign in to it. Checking
installation does not require profile authentication.

## Check the installation

```bash
cadrumo-mcp --help
```

If `cadrumo-mcp` is unavailable, install Cadrumo first; see
[Get Cadrumo](../download.md). The command and the `aeat` CLI ship in the same
Cadrumo distribution. The adapter connects to an already running local runtime.
An unavailable or untrusted endpoint returns a connection refusal; connecting
does not install or start a service.

## Register the server

The `--profile-id` argument is optional; see "Following your sign-in" below. To
name a profile, find its ID in Cadrumo. CLI output hides profile IDs by default;
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

Use a separate server entry for each profile you name. Keep credentials out of
the configuration. The server asks for no password when it starts. An agent can
sign in with your profile password through the `session` tool, either typed into
the call or by reference; the section "Give an agent a secret by reference"
below explains the form that keeps it out of the conversation. Whether you
start the server with `--credential-reference` decides how it connects.

**Following your sign-in.** Start the server without `--credential-reference`.
It follows your own Cadrumo sign-in for the selected profile. It answers
initialization, its tool list, the public tools (`authority` and
`corpus_search`) and operation discovery (`search` and `describe`) while nobody
is signed in. A tool that needs the profile makes
one attempt to resume your stored sign-in. With a live sign-in the call works.
With none it is refused with `authentication_required`: sign in to Cadrumo, then
call again. `--profile-id` is optional. Given alone, it is honoured only while
that profile is the selected one; otherwise profile calls return
`profile_mismatch`. Without it, the server acts for whichever profile is
selected.

Your sign-in governs this session. When you sign out, lock, or the sign-in
reaches its deadline, the session ends with it and profile calls are refused
until you sign in again. By default a sign-in ends 15 minutes after you enter
the password, and activity through MCP does not extend it.

**With an enrolled key.** Start the server with `--profile-id` and
`--credential-reference`. An approved protected credential reference, delivered
by the authorization flow below, can be supplied for a later connection while
its grant and the profile remain eligible. The server authenticates with the
enrolled key for that profile and works whether or not anyone is signed in.
`--credential-reference` without `--profile-id` is refused at start-up.

Either way, the `status` tool reports whether the connection's session is
`none`, `sign_in`, `typed_sign_in` or `key`, and which surface it serves.
`typed_sign_in` is a session the agent started with your profile password
through the `session` tool.

The optional `--surface NAME` argument pins the view of the server that the
connection is served. Without it the server uses `full`, which advertises every
tool and every operation the session may use. Choose `read-only-local` for an
agent that should only look: it leaves out the `review` and `respond` tools and
offers only operations that change no record and reach no network. Cadrumo's
local runtime enforces the surface when an operation is submitted, so hiding a
tool is not what keeps the agent read-only. An unknown name stops the server at
start-up, before any connection, and the error lists the surfaces available.

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

A connection that follows your sign-in needs no key. To let an agent work while
nobody is signed in, enroll one. On a first connection, ask the agent to use
`status`, then `authorization_prepare` and `authorization_request` for the
operations, periods and disclosures it needs. Review and approve that request in
Cadrumo's CLI or TUI. The agent uses `authorization_poll` to receive the
protected reference and `authenticate` to start an independently tracked
session. The `session` tool can instead sign the connection in with your profile
password, typed or by reference. That session is your own sign-in, with its
deadline, and not an independently tracked key session.

`search` ranks operations by the query, using their current contracts and
request vocabulary; omit the query to list them. `describe` shows a registered
operation's input contract. Both answer before admission too, and while Cadrumo
is not running: they then cover every registered operation on the connection's
surface and say `session` `none`, and after admission they cover the operations
the session may use. `search` returns ten summaries at a time; pass its
`next_cursor` back as `cursor` for the next page, and use `describe` for one
operation's full contract.
After admission, `execute` submits an operation and `observe`
tracks its result. The separate `authority` tool reads published tax authority
data. Operation grants, session locks, profile suspension, provider checks and
human review still apply. Retain operation IDs and reconcile uncertain effects
after a disconnect instead of submitting the same effect blindly. A call whose
outcome is not known is answered as unknown, not as an error, and its
`unknown_outcome` member says how to read what happened; do not repeat such a
call. For an operation that settled refused or failed, `result` returns the
recorded code, message and context in `error_detail`, as the command line
prints them.

Read a settled operation's approved projection with `result`. For a large result,
use `result_page` with the same result request and an initial page offset of zero.
Continue at the returned byte boundary, supplying the document digest from the
first page as `expected_digest`. Assemble and verify the complete document before
using it. Each page requires current authorization; a lock or revocation can stop
the remaining pages. An incomplete document is not a complete result.

To rotate or narrow an existing grant, reconnect with its protected credential
reference and prepare a new authorization request. Human approval is required
for the change. Revoking the grant prevents future admission under that key.

Discover the operations with `search`. An agent connected through MCP can run
every operation the command line can, with the same results, under the session it
holds. The packaged agent guidance has the agent tell you what it is about to do
before anything destructive or hard to reverse, and wait for your go-ahead in the
conversation. Calculations use Cadrumo's deterministic engine and published tax
authority. Connecting an agent does not authorize submission to AEAT. Review the
prepared filing yourself as described in the [filing guide](file-at-aeat.md).

## Give an agent a secret by reference

Some tools take a secret. The `session` tool takes your profile password to sign
in, to resume a locked profile or to change the password. The `installation`
tool takes it to import a profile archive or to enable recovery. The `execute`
tool takes one for an operation whose contract asks for it. A secret that you
type into the conversation has passed through the model and the client's
transcript before it reaches Cadrumo. To keep it out of the conversation, enter
it yourself, in a terminal of your own:

```text
cadrumo-mcp --hold-secret
```

The command asks for a label, so that you can recognise the secret in a listing,
and then for the secret twice, without showing what you type. It keeps the
secret in this computer's protected credential store and prints a reference.
Give the agent only that reference. The agent puts it in the argument whose name
ends in `_reference` (`secret_reference`, `new_secret_reference` or
`new_secret_confirmation_reference`) in place of the secret. The MCP server
reads the secret from the store and sends it to the local runtime on the same
protected channel that a typed secret uses. The secret never appears in the
conversation, in a tool result or in a log.

A secret held this way stays until you delete it, so the agent can sign in again
with the same reference after a lock or after your sign-in reaches its deadline.
To hold a secret for one use only, add `--once`. The first tool call that sends
the secret spends it: the server reads and deletes the stored copy immediately
before sending it to the runtime. A call that is refused before that point (an
invalid argument, a reference that holds nothing, no running runtime) leaves it
held. Once it has been read it is spent even if the send then fails; hold another
to try again.

```text
cadrumo-mcp --hold-secret --once
```

`cadrumo-mcp --list-held-secrets` lists what you have entered, by label and
without showing it, and `cadrumo-mcp --delete-held-secret REFERENCE` deletes one.
A secret that you entered is never shown back to you. A reference works only on
this computer and under your user account. While a secret is held, an agent
connected to this MCP server can use it by naming its reference, so delete a
password that you no longer want an agent to use. An agent still accepts a
secret that you type into the conversation; the reference is the form that keeps
it out.

## Storage, repair and other work that needs no profile

Some work needs no profile and no sign-in: inspecting and reclaiming storage,
resetting all profiles, listing profiles, inspecting and importing a profile
archive, enabling a recovery code, diagnosing and repairing the installation,
and verifying a review package or a calculation summary that you hold. The
`installation` tool does this work through the running local runtime, with one
`action` for each act, and gives the same result as the matching `aeat` command.
It is not a registered operation, so `search` does not list it; the tool's own
description names every action and its arguments. The terminal interface offers
the same work in **Installation**, which you can open from the sign-in screen.

A destructive action, such as reclaiming storage or resetting all profiles,
takes `confirm`. Unless `confirm` is true it changes nothing: it reports what it
would do, or refuses and says so, exactly as the command does without its
confirmation flag. The packaged agent
guidance has the agent show you that report and wait for your go-ahead before it
confirms. On the `read-only-local` surface the tool offers only the reads and
those reports.

### Read a recovery code that an agent enabled

An agent can enable a recovery code with the `installation` tool's
`recovery_enroll` action or the `session` tool's `enable_recovery` action. There
is no terminal to show the code on, and the code never appears in the
conversation or in a tool result. Cadrumo's runtime and the profile do not store
it. The MCP server keeps one copy in this computer's protected credential store
and gives the agent only a reference to it. Read the code yourself, in a
terminal of your own:

```text
cadrumo-mcp --show-held-secret REFERENCE
```

The command shows what the code was issued for and when, and then the code
itself. Write it down, then type `kept` to delete the stored copy. Press Enter
alone to leave it stored and read it again later. Until you confirm that you
have kept it, the copy stays in the credential store.

To list what is still held without showing any code, or to delete a copy
without reading it:

```text
cadrumo-mcp --list-held-secrets
cadrumo-mcp --delete-held-secret REFERENCE
```

These commands work only at a terminal. They refuse when their input or output
is redirected, so an agent cannot run them for you. If you delete a code that
nobody has kept, it is lost: disable recovery and enable it again to get a new
one. [Protect access to your data](protect-data-access.md) explains what a
recovery code is for and how to use it.

## Review and manage access as the profile owner

Use a human password-authorized session for the intended profile, as described
in [Set up a profile](profile-setup.md). Approve a request yourself
rather than leaving the agent to approve its own, and administer other clients from
your own session. Check the profile ID in each result.

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
