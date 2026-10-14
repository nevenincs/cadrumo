# Cadrumo tax-advisor harness data

This tree is the **operating layer** for an LLM tax-advisor agent that uses
Cadrumo's profile-bound MCP server. It is reviewed product data shipped inside
the harness wheel and read through `cadrumo_harness.resources`. It carries
no code and no secrets.

The Cadrumo engine computes tax deterministically for both CLI and MCP. The
harness is the **operating layer**: the agent orchestrates, extracts, classifies,
narrates, and hands off — but never computes a tax value itself.

Subtrees:

- `rules/` — the operator operating contract: always-on behavioural boundaries the
  agent loads every session. These are the operator analogues of the engineer-facing
  project rules, re-cast for the agent that *uses* the tool.
- `skills/` — executable workflow playbooks (preconditions, command sequence, JSON
  success assertions) for the canonical end-to-end tax flows.
- `reference/`: generated documents a rule sends the agent to. `command-operations.md`
  lists, for every command a skill names, the tools that do its work through MCP: the
  registered operations the command submits, which `execute` runs, and every other
  route, which is an operation for `execute` or a query for `authority`. A command
  whose work is the person's own act says so instead: signing in or out, locking,
  sessions, keys, passwords and other secrets, recovery, and installation work such as
  the profile list, storage, repair and resetting every profile. The three AEAT
  command groups that print help have no route. Authentication administration and
  the terminal interface belong to the separate runtime entrypoint.

You work only inside the profile of the person's explicitly reviewed attended
session, or the profile bound to the key configured for this MCP server. Start
with MCP `status`. Its session is `attended` when a person holding a live human
session approved this exact external connection, `key` when the configured key
admitted it, or `none`; it also names the surface the connection serves.

Without a key, the server requests attendance with an explicit finite surface
scope. The person signs in through Cadrumo, holds that human session, and reviews
this server's exact native request. MCP receives neither their password nor their
stored sign-in proof. A stored receipt alone does not admit MCP. With `none`,
every tool but `status` is refused, including operation discovery and public
reference queries. Follow the reply's `remedy` and ask the person to review the
required access; never treat a new sign-in as approval.

The status counts what the admitted session may disclose: `effective_scope`
carries `disclosure_count`, `disclosure_summary` with the count in each category,
and `disclosure_digest`, not the list itself. To read the entries, call `status`
with `disclosures` set to `offset` 0 and `expected_digest` to that digest, then
follow each page's `next_offset` until it is null. The runtime's
`config profile disclosures` controls and the terminal interface read the same
pages. Under a session, `search` and `describe` expose the operations allowed by
its scope and surface, while `authority` answers public tax queries. Public
reference content does not remove the tool server's admission requirement.
Discovery is not permission to execute an operation or release its result.

You never sign in, sign out, lock, list or deny sessions, request or approve a key,
change or reset a password, enrol recovery, or act outside your profile, and you
never ask for a password, a key or any other secret. No tool takes one. An operation
whose contract needs a secret or administers keys is the person's own act: it is
refused with `person_act_required`, and its `remedy` says to ask the person to do it
in Cadrumo. Tell the person what is needed and stop that step.

An attended lease follows its exact human parent and ends no later than that
parent. Sign-out, lock, parent expiry or loss of the held connection retires that
access. MCP activity extends neither the idle nor absolute sign-in deadline.
While the same parent and approved connection remain live, the runtime may renew
a short child lease within that existing approval. A fresh connection or new
parent requires another exact review. Selecting another profile never moves this
server's access to it; follow the refusal and start a separately reviewed session.

For access without a live human parent, the person arranges a finite enrollment
proposal through the installed requester SDK or
`cadrumo-runtime config profile automation create` with its protected proposal
input. Preparation binds the proposal to the runtime-minted delivery destination.
A separate person session inspects the exact request and review digest and
approves its operations, actions, periods and disclosure categories. Submission
alone issues no key. Only completed protected native delivery supplies the
credential reference used to start MCP with `--profile-id` and
`--credential-reference`; no raw key goes into the conversation.

A configured key grants only its approved scope, further narrowed by the MCP
surface. The harness's agent-key policy derives a finite operation list from
registered contracts and excludes the person's own acts. Its required categories
are profile values and operation metadata; tax values require explicit additional
approval. A result outside the granted categories is refused. The server retains
a live key session without authenticating on every healthy call. After retirement,
transport loss or refusal it may authenticate again with the same configured
reference, at most once per call; this neither approves a request nor revives an
expired, revoked or locked grant. Requesting, renewing, rotating or changing the
scope of a key remains the person's act in Cadrumo.

A lost reply is not proof that an operation failed or settled. Retain operation
receipts and reconcile uncertain effects after reconnecting.
