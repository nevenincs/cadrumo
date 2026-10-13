---
tags:
  - '#adr'
  - '#desktop-agent-host'
date: '2026-10-12'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:87d2519edf6284d781f4c16447f18dc30d737879b9e6bc422a87004a2724ca75'
related:
  - "[[2026-10-12-desktop-agent-host-reference]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr]]"
  - "[[2026-10-12-mcp-parity-attended-live-sign-in-adr]]"
  - "[[2026-10-10-mcp-parity-shared-sign-in-door-adr]]"
  - "[[2026-06-10-llm-evidence-classification-adr]]"
  - "[[2026-06-10-ledger-evidence-enforcement-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-adr]]"
  - "[[2026-10-06-desktop-shell-capabilities-shell-profile-reads-adr]]"
  - '[[2026-10-04-application-sign-in-adr]]'
  - '[[2026-10-12-runtime-manager-architecture-caller-owned-root-adr]]'
---

# `desktop-agent-host` adr: `The desktop hosts the agent through a Cadrumo launcher, with agent state encrypted inside the profile's storage boundary and explicit consent before any provider receives private content` | (**status:** `proposed`)

## Problem Statement

The desktop agent column (design approved 2026-10-12) needs the cadrumo-agent service running for the signed-in profile. On 2026-10-12 the owner ruled, first-hand, on five points this record must honour:

- Protection at rest: private profile data, conversations and attachments stay under Cadrumo's encrypted-storage requirement; no plaintext exchange folder.
- Consent: explicit consent before private content goes to an external model provider, naming the provider and the content; signing in, attaching a file or approving an operation never implies it; passwords and authentication secrets stay outside the agent and provider boundary.
- Shipping: a compatible cadrumo-agent ships inside Cadrumo's package through the normal build and release; compatibility is defined; absence or incompatibility fails clearly; nothing is downloaded or installed at runtime.
- Rust ownership: the Tauri technical session implements the host from a contract given to it; no competing Rust workstream.
- Location: agent state lives within the selected profile's storage boundary, respecting the explicit storage-root override, resolved and supplied by Cadrumo; no global agent root; the agent cannot choose another profile's location; a profile-local folder alone is not encryption.

cadrumo-agent today stores conversation content in plaintext SQLite, log files, replay rows and a provider's own transcripts, cannot start in hosted mode, and ships beside Cadrumo rather than inside it; several of its accepted records rule the opposite of the owner's rulings (`2026-10-12-desktop-agent-host-reference`). This record fixes the cross-project contracts before anything is built.

## Considerations

- The shell holds no runtime connection and launches only fixed product children (`2026-10-04-desktop-shell-adr`). A long-lived `aeat` child holding a connection has a precedent in `config sign-in-hold` and in `cadrumo-runtime --configured-root`'s standard-input lifetime (`2026-10-12-desktop-agent-host-reference`).
- Every client on the person's OS login resumes the live sign-in, terminal or not, and no frontend receives key material (`2026-10-04-application-sign-in-adr`, amended 2026-10-12).
- The agent lives inside the one signed-in profile, never authenticates, never handles a secret, and is admitted by resume, a person-issued key or attendance (`2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr`, `2026-10-12-mcp-parity-attended-live-sign-in-adr`).
- Decrypted document bytes live only in memory; bytes never enter MCP results, only registered projections; consent is per invocation and digest-bound (`2026-06-10-llm-evidence-classification-adr`, `2026-09-26-mcp-purpose-authentication-adr`).
- The capsule directory is content-inventoried and published as an immutable unit; live agent files there would block profile deletion (`2026-10-12-desktop-agent-host-reference`).
- cadrumo-agent's stores open before any configuration is read, in three processes; every opener must take the key first (`2026-10-12-desktop-agent-host-reference`).
- The Claude Code lane writes its own plaintext transcripts, credentials and cache, some outside the agent root, beyond cadrumo-agent's control (`2026-10-12-desktop-agent-host-reference`).

## Considered options

Process topology:

- **Shell starts a Cadrumo launcher (`aeat agent serve`), which starts and supervises the agent (proposed).** The shell still runs only digest-verified `aeat`; the launcher, a Cadrumo client, holds the connection, resolves the location and supplies the key; session retirement reaches it as a pushed event.
- Shell starts cadrumo-agent directly. Rejected: the shell would have to obtain the location and the key, which needs a runtime connection or key material in the shell.
- Runtime manager supervises the agent. Rejected: the manager holds no profile or session authority.

Agent state at rest:

- **Encrypted stores in a profile-scoped sibling root `<storage-root>/agent/<profile-id>/`, keyed by a per-profile agent data key held in Cadrumo custody (proposed).** Bounded change to cadrumo-agent (one SQLCipher connector); enrolled in profile deletion as its own step.
- Agent state as Cadrumo secure objects in the bucket database. Kept as the alternative: no key leaves Cadrumo, but cadrumo-agent's SQL and checkpoint stores would move behind Cadrumo's IPC, a much larger change.
- Inside the capsule directory. Rejected: breaks deletion preflight and capsule immutability.

Launcher identity:

- **A new `agent-host` frontend that may resume the stored sign-in, may receive only the agent data key and the provider credential on a dedicated door, and is refused every person act (proposed).**
- The CLI frontend with a narrow door. Rejected: a CLI session can sign out, delete and approve.

Lanes in hosted mode:

- **Direct Anthropic API lane only (proposed).** Runs in process; all its state goes through the encrypted stores.
- Claude Code lane. Excluded until a run proves nothing persists in plaintext.

Webview access:

- **Closed list of token-checked host commands and a Tauri channel for the stream (proposed).** The CSP stays closed; the bearer stays in the Rust host.
- Open the CSP to the local service. Rejected.

## Constraints

Binding if accepted:

- The shell holds no runtime connection, session, receipt, password, provider credential or agent data key. It never signs in for the agent.
- Agent state lives only under `<storage-root>/agent/<profile-id>/`, derived by Cadrumo from the resolved storage root (honouring `CADRUMO_LOCAL_STORAGE_ROOT`) and the launcher's bound profile. The agent receives that one path and no other; it never receives the storage root or another profile's id.
- Every byte cadrumo-agent persists under that root that can hold private content is encrypted with the profile's agent data key. Nothing private is written to plaintext logs, temp files, token files, workspaces or provider homes. Files that hold no private content (ready record, store-format marker) may stay plaintext.
- The agent data key and the provider credential travel only Cadrumo custody → runtime door → launcher memory → agent standard input frame → worker standard input pipe, and are never placed in environment variables, files, command lines, transcripts or the webview. Cadrumo passwords and receipts never cross into the launcher's child or the provider.
- No real document is written in plaintext to the agent root. Documents live in Cadrumo custody; the model reads only registered projections served by Cadrumo.
- Owner ruling of 2026-10-13, first-hand, relayed by the desktop design session: "tool calls are approval gated not messages". It replaces per-message consent. Sending a message is the person's own act and needs no further grant. Every tool call waits on the person's approval, given by a deliberate gesture that the model cannot make. Off-host document extraction keeps its existing digest-bound acknowledgement (`2026-06-10-llm-evidence-classification-adr`).
- A missing or incompatible bundled agent is a typed refusal shown in the agent column; Cadrumo never downloads or installs it.
- Unbuilt capability is shown as unavailable; no mock host or simulated behaviour.

Affected prior rulings, each needing its own amendment once this is accepted: `2026-10-04-desktop-shell-adr` (a long-lived `aeat` child and the agent host commands), `2026-10-04-application-sign-in-adr` (the `agent-host` key door; its resume needs no exception since that record's 2026-10-12 amendment admits every client), `2026-06-10-llm-evidence-classification-adr` (consent grants for hosted-assistant projections), `2026-10-12-mcp-parity-agent-inside-the-signed-in-profile-adr` (consent and key delivery as person acts or doors), and in cadrumo-agent's vault the conversation-data-posture, profile-data-root, shipping-and-versioning, project-boundary and hosting-contract records.

## Implementation

We will host cadrumo-agent through a Cadrumo launcher started by the shell, keep agent state encrypted in a profile-scoped root Cadrumo supplies, keep documents in Cadrumo custody, and require explicit per-provider consent before private content leaves the machine.

Contract 1, shell and launcher (owner: Tauri technical session):

- Start `aeat agent serve` (digest-verified, projected environment) only while sign-in is present and the runtime available. Write one JSON frame on its standard input: a freshly minted gateway bearer token. Keep standard input open.
- Read one `agent_ready` line (gateway port, agent version, hosting-contract version) or one typed refusal (`agent_service_absent`, `agent_service_incompatible`, `agent_signed_out`) from standard output; show refusals in the column. Missing consent is not a start refusal; it is handled per send.
- Stop by closing standard input on sign-out, unknown state, runtime unavailable, active-profile change, version change or window close; then wait for exit, and end the process tree if it overruns a bounded deadline.
- Serve the webview through a closed list of token-checked commands mapped one-to-one to gateway routes and Cadrumo operations, and the run stream through a Tauri channel.
- Read results carry raw values; the webview words them in the chrome locale. A conversation is `{id, title, last_active_at (ISO instant), document_count, archived}`. A document is `{id, name, media_type, size_bytes, role, status, members?}`, keyed by conversation id. A conversation's history is a list of turns, oldest first, projected from the run history. Each turn is one of three shapes: a person turn `{id, text, sent_at, files?: [{id, name, media_type}]}`, an agent turn `{id, text, state, failure_reason?}`, or a tool turn `{id, label, state, detail?}` whose label is worded by Cadrumo. A host that offers no agent reads makes the column show every agent action as unavailable. Loading and refusal are distinct states and are never shown as empty (hypothesis: names follow the desktop's current `agentViews` interface).
- Choosing files opens the native file dialog in the Rust host. The host returns opaque handles with display name, size and media type to the webview. Paths stay in the host and go only to the documents-add operation's `aeat` child.

Contract 2, launcher (owner: Cadrumo backend):

- Admit on the `agent-host` frontend by resuming the stored sign-in; bind the selected profile; refuse with `agent_signed_out` otherwise.
- Verify the bundled agent against the package manifest and the supported range; resolve and create the profile's agent root; obtain the agent data key and provider credential from the runtime door.
- Start `python -m cadrumo_agent serve` with the hosting-contract environment and a standard-input frame carrying the key, provider credential and the shell's bearer; wipe its copies.
- Supervise: on session retirement, re-resume once and stop the agent if refused; on standard-input close, cancel the live run, shut the agent down, end and confirm the process tree.

Contract 3, agent root and key (owner: Cadrumo backend):

- A storage-taxonomy category and scope for `<storage-root>/agent/<profile-id>/`, and a deletion journal step and owner receipt that remove it during profile deletion and all-profile reset.
- A per-profile agent data key: random, minted on first use, stored as a SECRET, profile-local, process-local secure object; released only on the `agent-host` door to the admitted launcher.

Contract 4, cadrumo-agent storage (owner: cadrumo-agent):

- One SQLCipher connector used by every store opener, keyed from the standard-input frame before any store opens; a store-format identity that refuses plaintext or wrongly keyed stores.
- No log files in hosted mode; worker standard error not written to disk; no `service.token` or IPC secret files; `tmp` and `scratch` emptied after every run.
- Hosted lanes limited to the direct Anthropic lane; documents read through Cadrumo projections, not workspace files.

Contract 5, documents (owner: Cadrumo backend):

- Add by path into custody with a typed conversation link and role; ZIP expanded in memory under member-count, expanded-size, nesting and link bounds, each member stored individually; refusals reported per file.
- List by conversation; text projections per document for the hosted assistant; ledger-data documents continue through the existing evidence and import operations with human review.
- Deleting a conversation removes its links; bytes go only when unreferenced and not under hold.

Contract 6, approvals (owner: desktop host; cadrumo-agent):

- Per-message consent grants are withdrawn by the 2026-10-13 ruling. No grant, withdraw or list operations exist.
- cadrumo-agent raises a `permission_request` for each tool call. The desktop shows it, and only a person's gesture answers it, on the gateway's permission route.
- Cadrumo reviews raised by the agent's MCP session are answered only through a person door. That door's form is open (`2026-10-13-desktop-agent-host-live-lane-review-audit`, `review-door-for-agent-reviews`).

Contract 7, packaging and compatibility (owner: Cadrumo build; cadrumo-agent):

- cadrumo-agent is never published to PyPI or any public index. Owner ruling of 2026-10-12, first-hand: "we will not publish cadrumo agent to pypi, ever. we do not have a settled method of provisioning the repo." How its source is provisioned into Cadrumo's build is open (remaining choice 5). Today's wheel selector admits only hashed PyPI registry wheels, so whichever method is chosen must change that selector deliberately. Once provisioned, Cadrumo declares the launcher script, and the package manifest carries an agent statement (bundled, distribution version, hosting-contract version, store-format version) checked like the user-docs statement.
- Cadrumo declares the supported agent version range and contract versions; the launcher compares them with the manifest and with `cadrumo-agent version --json` before start.
- Both products use the latest Anthropic SDK release as their floor (1.13.0 on 2026-10-12), with no compatibility path for older SDK versions. Parameters the SDK removed, such as `temperature`, are dropped rather than shimmed. Owner ruling of 2026-10-12, first-hand: "ensure we're working against the latest anthropic versions, no backwards or old version support."
- Claude model names are never hardcoded. They come from the Anthropic Models API, which gives id, display name, creation time, input and output limits, and a capability tree, and needs are expressed as capability requirements. Owner ruling of 2026-10-12, first-hand: "model names should be derived programmatically from the api!" The API carries no price and no tier, so how a model is chosen per role, and what replaces Cadrumo's per-model price table, is open (remaining choice 6). Node is not bundled while the Claude Code lane is excluded.

Migration implications:

- Cadrumo: new namespaces (agent data key, consent grants), a new storage scope and category, a new deletion journal state and owner value, a package-manifest statement, an attachment-manifest schema version (conversation link, agent source), and the `anthropic` major upgrade. Readers must accept the previous attachment-manifest version; no existing profile data is rewritten.
- cadrumo-agent: superseding records for the five affected decisions; a hosting-contract version bump (key frame, bearer from the host, no token files); a store-format version. No hosted data can exist today because hosted start is refused, so plaintext stores are refused and re-created rather than converted.
- Desktop: the shell amendment; the CSP is unchanged.

Verification criteria (each on the packaged build with a synthetic encrypted profile, no mocks of the component under test):

1. Package: the manifest's agent statement matches the installed distribution; removing it or changing its version yields `agent_service_absent` or `agent_service_incompatible` in the column, and nothing is downloaded.
2. Lifecycle: the launcher and agent start only while signed in, and stop on sign-out, lock, idle and absolute expiry, runtime restart, profile switch and window close, leaving no process. The shell never holds a runtime connection, key or credential (process and memory inspection of the host's IPC traffic and arguments).
3. Location: with and without `CADRUMO_LOCAL_STORAGE_ROOT`, agent state appears only under that root's `agent/<profile-id>/`; a second profile's root is never touched; profile deletion and all-profile reset remove it, with receipts.
4. At rest: after a real conversation with a document, a byte scan of the storage root, the OS temp directory and user cache directories for known message, tool-result and document strings finds none outside encrypted stores; the stores do not open without the key.
5. Secrets: the agent data key, provider credential, gateway bearer and Cadrumo password appear in no environment block, command line, file, log or transcript.
6. Approvals: every tool call waits on the person's decision, a rejected call does not run, and the model cannot answer its own request.
7. Tool path: a real, signed-in Cadrumo read through the hosted assistant succeeds and is refused after sign-out; no sign-in, sign-out, lock, attendance or secret-carrying tool is reachable. This is recorded as cadrumo-agent's tool-access proof and pairs with `2026-10-10-mcp-parity-plan` `P10.S70`.
8. Documents: each accepted type, a ZIP and a ZIP bomb fixture; custody digests, conversation links, refusals with reasons, ledger-data documents reaching review, deletion with holds.
9. Interface: the column shows every unbuilt or refused capability as unavailable with its reason.

## Rationale

The launcher puts every authority act where authority already lives: in a Cadrumo client admitted by the runtime. The shell keeps its no-connection rule because it only starts and stops a product command, and the launcher receives pushed retirement events the shell cannot. A profile-scoped sibling root satisfies the location ruling without disturbing the capsule's deletion and publication guarantees, and encrypting it with a Cadrumo-held key satisfies the at-rest ruling with the smallest change to cadrumo-agent. Keeping documents in custody and serving projections is the only route that meets the at-rest ruling and the MCP byte rule together. Consent as a person act tied to provider, model and content meets the consent ruling and keeps it out of the agent's reach.

## Consequences

- The column can be built now against these contracts, with each capability unavailable until its owner delivers it.
- Releasing an agent data key to a client process is new and needs the owner's explicit acceptance through the sign-in amendment.
- The Claude Code lane is unavailable for real data until proven; the direct lane cannot read images or PDFs itself, so document understanding rests on Cadrumo's readers.
- The owner ruled on 2026-10-12, under `2026-10-04-application-sign-in-adr`, that a message the person sends to the assistant counts as their activity. Until that extension is built, conversations end at the sign-in's idle deadline.

Remaining architectural choices, each named for the owner:

1. Agent state shape: encrypted sibling root with a released key (proposed) or agent state as Cadrumo secure objects with no key release.
2. Launcher identity: a new `agent-host` frontend (proposed) or the CLI frontend with a narrow door.
3. Withdrawn by the 2026-10-13 approval ruling: no consent granularity remains to choose.
4. Implementation owner for the Tauri host: no running session claims `native/desktop/src-tauri`.
5. How the cadrumo-agent repository is provisioned into Cadrumo's build, given that it is never published to PyPI.
6. Model selection per role from the live Models API: which model to use when several meet a role's capability needs, and what replaces the per-model price table.
