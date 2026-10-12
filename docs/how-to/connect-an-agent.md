# Connect an agent (MCP)

The installed `cadrumo-mcp` command connects an MCP client to Cadrumo's local
runtime. A connection works in one of three ways: it follows your own Cadrumo
sign-in, it uses a key you issued for one profile, or you approve it to follow a
sign-in you hold open (see "Hold a sign-in for an agent" below). Whichever way,
the agent works only inside that one profile, never signs in and never handles
a secret. With none of these it answers only its tool list and `status`,
which tells it to ask you to sign in to Cadrumo. The client can run only
operations allowed by its current session and, for a key, its grant.

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
the configuration and out of the conversation. The agent never signs in and never
handles a password, a key or any other secret: no tool takes one. It works only
inside the one profile you are signed in to, or the profile of a key you issued
and configured for it. Whether you start the server with `--credential-reference`
decides how it connects.

**Following your sign-in.** Start the server without `--credential-reference`.
It follows your own Cadrumo sign-in. While nobody is signed in it answers only
its tool list and `status`, which says to sign in to Cadrumo; every other tool,
including `authority`, `corpus_search`, `search` and `describe`, is refused with
`authentication_required` and a `remedy` that tells the agent to ask you to sign
in. A tool call makes one attempt to resume your stored sign-in; with a live
sign-in the call works. `--profile-id` is optional. Given, it is honoured only
while that profile is the selected one. Without it, the server is bound to the
profile of the first sign-in it resumes and stays bound to it: if you then sign in
to another profile, every call is refused with `profile_mismatch`, and you start a
new agent session for the other profile.

Your sign-in governs this session. When you sign out, lock, sign in to another
profile, or the sign-in reaches its deadline, the session ends with it and calls
are refused until you sign in again. By default a sign-in ends 15 minutes after
you enter the password, and activity through MCP does not extend it. Only one
profile is signed in at a time: signing in to another profile signs the first out
everywhere, its agent sessions included.

**With a key you issued.** Start the server with `--profile-id` and
`--credential-reference`. Issue the key yourself with `aeat config profile
automation create`, review and approve it as described below, and put the
protected credential reference it delivers in the server's configuration. The
server authenticates with that key on every call while the key's grant and the
profile remain eligible, whether or not anyone is signed in.
`--credential-reference` without `--profile-id` is refused at start-up. If the
key cannot authenticate, the server keeps answering `status` with the refusal and
refuses everything else; restore access, or issue a replacement key and change the
configuration.

Either way, the `status` tool reports whether the connection's session is `none`,
`sign_in` or `key`, and which surface it serves.

The optional `--surface NAME` argument pins the view of the server that the
connection is served. Without it the server uses `full`, which advertises every
tool and every operation the session may use. Choose `read-only-local` for an
agent that should only look: it leaves out the `review` and `respond` tools and
offers only operations that change no record and reach no network. Cadrumo's
local runtime enforces the surface when an operation is submitted, so hiding a
tool is not what keeps the agent read-only. An unknown name stops the server at
start-up, before any connection, and the error lists the surfaces available.

Under a session, `corpus_search` searches the bundled BOE/AEAT corpus and approved
tax terminology. Supply `query` and optionally `limit` (1–50). An exact citation
ID returns its published verbatim text; other queries return ranked offline
evidence and terminology matches. The response identifies the publication
generation used for citation lookup.

## Work through the connection

`search` ranks the operations the session may use by the query, using their
current contracts and request vocabulary; omit the query to list them. `describe`
shows a registered operation's input contract. `search` returns ten summaries at
a time; pass its `next_cursor` back as `cursor` for the next page, and use
`describe` for one operation's full contract. `execute` submits an operation and
`observe` tracks its result. The separate `authority` tool reads published tax
authority data. Operation grants, session locks, profile suspension, provider
checks and human review still apply. Retain operation IDs and reconcile uncertain
effects after a disconnect instead of submitting the same effect blindly. A call
whose outcome is not known is answered as unknown, not as an error, and its
`unknown_outcome` member says how to read what happened; do not repeat such a
call. For an operation that settled refused or failed, `result` returns the
recorded code, message and context in `error_detail`, as the command line prints
them.

Read a settled operation's approved projection with `result`. For a large result,
use `result_page` with the same result request and an initial page offset of zero.
Continue at the returned byte boundary, supplying the document digest from the
first page as `expected_digest`. Assemble and verify the complete document before
using it. Each page requires current authorization; a lock or revocation can stop
the remaining pages. An incomplete document is not a complete result.

An agent connected through MCP can run every operation the command line can run
inside its profile, with the same results, under the session it holds. The
packaged agent guidance has the agent tell you what it is about to do before
anything destructive or hard to reverse, and wait for your go-ahead in the
conversation. Calculations use Cadrumo's deterministic engine and published tax
authority. Connecting an agent does not authorize submission to AEAT. Review the
prepared filing yourself as described in the [filing guide](file-at-aeat.md).

## Acts that stay yours

Some acts are yours alone, and the agent is refused them with
`person_act_required` and a `remedy` that tells it to ask you: signing in or out,
locking, listing or denying sessions, requesting, approving, rotating or revoking
keys, changing or resetting the password, enabling or using recovery, and any
operation that needs a password, a key or another secret, such as configuring a
certificate secret or exporting the profile bundle. So is your consent to send a
stored document to a hosted model: the agent may ask for the extraction that stays
on this computer, but an extraction off it carries your acknowledgement, which you
give yourself. So is work that belongs to no single profile: inspecting and
reclaiming storage, resetting all profiles, listing profiles, inspecting and
importing a profile archive, diagnosing and repairing the installation, and
verifying a review package or a calculation summary that you
hold. Do these with the matching `aeat` command, or in the terminal interface,
which offers the installation work in **Installation** from the sign-in screen.

## Review and manage access as the profile owner

Use a human password-authorized session for the intended profile, as described
in [Set up a profile](profile-setup.md). Issue a key with `aeat config profile
automation create`, approve it yourself, and administer every client from your own
session; an agent never requests, approves or changes a key. Check the profile ID
in each result.

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
a recorded decision alone does not prove completed protected delivery. Put the
delivered reference in the MCP server's configuration with `--credential-reference`.

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

Confirm the returned grant IDs. An agent's next call then resumes your sign-in, or
authenticates again with its configured key.

## Run an agent on separate storage

An agent harness, an evaluation or a test can use its own Cadrumo data, kept
apart from yours. Choose a new, empty directory for it. Give every Cadrumo
program you start for it the same two settings: `CADRUMO_LOCAL_STORAGE_ROOT`
names the directory, and `CADRUMO_SECRET_STORE_DIR` names a directory for its
encrypted secret store. Both must be absolute paths.

Cadrumo's own background service serves only your usual data. For a separate
directory, your harness starts Cadrumo's runtime itself and decides when it
stops. The `cadrumo-runtime` command is in the same `bin` directory as `aeat`
and `cadrumo-mcp`:

```text
cadrumo-runtime --configured-root
```

- **Start.** Run the command with the two settings in its environment and with
  its standard input and standard output connected to your process. It serves
  the directory that `CADRUMO_LOCAL_STORAGE_ROOT` names. `aeat`, the terminal
  interface and `cadrumo-mcp`, started with the same two settings, find it on
  their own.
- **Ready.** When clients can connect, it writes one line of JSON to standard
  output, for example
  `{"kind":"runtime_ready","pid":4242,"product_version":"…","storage_identity":"…"}`.
  It writes nothing else there. `aeat --format json config sign-in-status`,
  run with the same settings, also succeeds once it is ready.
- **Stop.** Close its standard input. It finishes the work in progress and exits
  with code 64. If your process ends, its standard input closes too, so the
  runtime does not outlive it. Do not start it with standard input from the null
  device, because then it stops at once. At a terminal, Ctrl+C stops it with
  code 65.
- **Refusals.** It exits with code 68 and prints `runtime_root_mismatch` when
  `CADRUMO_LOCAL_STORAGE_ROOT` is not set, or when the directory is your usual
  Cadrumo data directory, lies inside it or contains it. It creates nothing
  then. It exits with code 67 when a runtime already serves the directory. Add
  `--expected-version VERSION` to refuse, with code 69, a package of another
  version.

Profile passwords, enrolled keys and the operations each session may run work
exactly as they do on your usual data. Pass each secret on the command's
protected channel and never on the command line or in an MCP tool call.

### Hold a sign-in for an agent

A sign-in made with `aeat config login` is kept in this computer's protected
credential store, and `cadrumo-mcp` follows it from there. A Windows logon that
holds no credentials cannot use that store; there, or in a harness that should
leave nothing behind, hold the sign-in instead:

```text
aeat --format json config sign-in-hold agent-test
```

The command signs in to the profile and keeps that sign-in open, without
storing it, for as long as its standard input stays open. Nothing in it is
written to the credential store or to the profile's storage.

- **Password.** The first line of standard input is one JSON object,
  `{"passphrase": "…"}`. It is read once and then discarded.
- **Events.** Standard output carries one JSON object per line, each naming its
  `event`:
  - `held` gives the `profile_id` and the `session_expires_at` deadline.
  - `attendance_request` reports an MCP connection that asks to follow this
    sign-in. It gives the `attendance_id`, the `process_id` of the asking
    process as the operating system reports it, the `frontend`, the `surface`
    and when the ask lapses (`expires_at`, two minutes after it was made).
  - `attendance_decided` and `attendance_refused` report your answers.
  - `signed_out` and `session_ended` report the end of the sign-in.
  - `ended` comes last, with the `reason`: `input_closed`, `signed_out` or
    `session_ended`.

  The command's result follows the events.
- **Decisions.** Each later line of standard input is one JSON object:
  `{"approve": "ATTENDANCE_ID"}`, `{"decline": "ATTENDANCE_ID"}`, or
  `{"sign_out": true}`. Approve only an ask whose `process_id` is the
  `cadrumo-mcp` process you started, or one of its descendants. Nothing else
  admits a connection: not a profile ID, a storage path, the runtime's
  endpoint, or an attendance ID copied to another process.

Start `cadrumo-mcp` with the same two settings and without
`--credential-reference`. When it has no stored sign-in to follow, its first
call that needs the profile asks the holder to admit it, and waits up to 90
seconds for the answer. Once approved, its `status` tool reports `"session":
"attended"`. The agent then works inside that profile, under the served surface
and the same operation, approval and disclosure checks as any session. An
operation that only the person may run, such as signing in or managing keys, is
refused to it. The approval holds for that one MCP connection while the held
sign-in lives. When its short lease runs out, it is renewed without a new
decision.

Access ends for every connection that follows the held sign-in when any of these
happens, and each later call is refused:

- the holder's standard input closes, or the holder exits;
- you send `{"sign_out": true}` to the holder;
- another process signs the person out with
  `aeat --format json config logout --secrets-stdin`, reading
  `{"passphrase": "…"}`;
- the profile is locked with `config profile lock --all`;
- the sign-in reaches its deadline: by default 15 minutes after you entered the
  password, and agent activity does not extend it;
- the runtime stops.

A command that runs without a terminal reads its profile password from the root
`--profile-secrets-stdin` channel as `{"profile_passphrase": "…"}`; see
[Protect access to your data](protect-data-access.md). It never follows a held
sign-in. In full, with the two settings in the environment of every command:

```text
cadrumo-runtime --configured-root
aeat --format json config profile create agent-test --quiet --secrets-stdin
aeat --format json config sign-in-hold agent-test
cadrumo-mcp
aeat --format json --profile-secrets-stdin config profile status
```

`profile create` reads `{"passphrase": "…", "passphrase_confirmation": "…"}`.
Keep the holder's input open while the agent works, and approve its ask when it
arrives.

When you are done, close the holder's input, close the MCP client, close the
runtime's standard input and wait for it to exit with code 64, then delete the
directory. Nothing in your usual Cadrumo data is read or changed along the way.
