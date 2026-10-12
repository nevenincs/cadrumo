---
tags:
  - '#adr'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-12'
body_schema: 'body-v2'
body_hash: 'sha256:ef1b9711d5650b6a9858b2615680f3f0f28441613a6cce429fca33cd5f79f0eb'
related:
  - "[[2026-10-10-mcp-parity-parity-mechanism-options-research]]"
  - "[[2026-10-10-mcp-parity-surfaces-and-registry-reference]]"
  - "[[2026-10-10-mcp-parity-admitted-surface-defects-reference]]"
  - "[[2026-10-10-mcp-parity-closed-operations-reference]]"
  - "[[2026-09-26-mcp-purpose-authentication-adr]]"
  - "[[2026-07-02-agent-harness-refoundation-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
---
# `mcp-parity` adr: `The MCP server reaches parity through the operation registry and its existing generic tools, never through the command line` | (**status:** `accepted`)

## Problem Statement

Cadrumo's command line and terminal interface implement the tax work. Its MCP server
advertises sixteen tools and reaches 116 of 266 registered operations; 143 operations do
not admit it. The owner asked how the MCP server becomes a full interface for that work,
and named three candidates to weigh instead of assuming everything is rebuilt: a direct
call to the existing command line, a native MCP call per operation, or a generalized
command-line wrapper. The choice fixes where parity is defined, where authority is
enforced and what a consuming agent can pin, so it has to be made before any operation is
opened.

Records named `2026-10-10-cadrumo-integration-...` belong to the vault of the cadrumo-agent repository, a separate project that drives this application through its MCP server; they are cited by name and are not in this vault.

## Considerations

- The MCP server is already a generic envelope over the operation registry: nine of its
  tools search, describe, submit, observe, read, review and control any registered
  operation the session may use (`2026-10-10-mcp-parity-surfaces-and-registry-reference`).
- For handling an operation it is more general than the command line, which has no way to
  observe, resume or cancel an operation by identifier after the command exits (same
  reference).
- Most command-line commands only submit a registered operation, through one generic
  function called from hand-written sites (same reference).
- A complete machine-readable manifest of the command line exists and nothing consumes
  it, so a command-line envelope is a real option and not a strawman
  (`2026-10-10-mcp-parity-parity-mechanism-options-research`).
- Cadrumo's accepted MCP record rejects command-line wrappers as the MCP execution path,
  and its accepted architecture record has all three surfaces dispatch registered
  operations through the supervisor (same research).
- A command-line call presents as the command-line frontend, returns no operation
  identifier to observe, and answers a review inside the command where the caller never
  sees it (same research).
- The consuming agent pins tool names exactly and asks for the tool list before any
  session exists (same research).
- Admission is explicit per definition, and 65 exclusions carry no stated reason
  (`2026-10-10-mcp-parity-closed-operations-reference`).
- Several operations that already admit MCP lack the safeguard the command line applies,
  and some safeguards live in a command handler or a screen and not in the operation
  (`2026-10-10-mcp-parity-admitted-surface-defects-reference`).
- The owner, on what the product delivers: "the end results for us is a filing
  calculation, an exported BOE artefact or a google sheet but not an actual AEAT write.
  We pull and sync information (one directional, never bi-directional)"
  (`2026-10-10-cadrumo-integration-owner-rulings-research`, typing lightly corrected).
  A full MCP interface therefore ends at calculation and local export.
- The owner separately wants the agent itself to have Cadrumo's command line and Python
  (`2026-10-10-cadrumo-integration-owner-rulings-research`). That is the agent's own door.
  It is not a mechanism for the MCP server, and it changes what MCP admission is for:
  typed, observable, reviewable access, not reach.

## Considered options

- **One native MCP tool per operation.** Each tool would carry its own schema. Rejected:
  the tool list would change with every operation, which breaks a consumer that pins
  names, and it rebuilds the second catalogue this branch of Cadrumo deleted.
- **A generic "run a command" tool over the command line's manifest.** Fastest route to
  breadth. Rejected: it reverses an accepted Cadrumo ruling, makes per-frontend admission
  meaningless, loses operation identifiers and review steps, and needs a process and a
  login per call.
- **Targeted command-line calls for a few capabilities.** Rejected: no capability was
  found for which it beats registering an operation or adding a public reference
  sub-query.
- **Admit every operation to MCP unless an exclusion is recorded.** Rejected as a default:
  it inverts the registry's rule that a frontend is never granted silently, and makes
  adding MCP the cheap way to pass a check. (Overtaken on 2026-10-11:
  `2026-10-11-mcp-parity-full-parity-adr` admits every operation, with no exclusion.)
- **The operation registry behind the existing generic tools, with admission decided and
  recorded per operation.** Chosen.

## Constraints

Binding:

- The MCP server never performs work by invoking the command line, for any capability.
  This binds the MCP server. It does not restrict an assistant's own use of Cadrumo's
  command line, which the accepted `2026-10-10-cadrumo-integration-terminal-access-adr`
  governs; that record keeps the tool path as the default door for reading and for
  anything long-running, reviewed or needing an exact identifier, and this record is how
  that door is filled.
- No tool name is added for a tax operation. New capability reaches MCP as a registered
  operation, or as an argument or sub-query on an existing tool.
- A surface served to a particular client is named. The name fixes what a client pins:
  the surface's tool names, and its declared properties, which are whether anything on it
  can change the profile's records and whether anything on it reaches the network. A
  surface whose tool names or declared properties change gets a new name. Its operation
  list is held by Cadrumo, is fixed within a Cadrumo release, and may grow between
  releases only within the declared properties. Adding an operation that way keeps the
  name, so admitting a family needs no release of the consuming agent. A surface may
  narrow what the registry admits and never widens it.
  A surface is enforced by the server when an operation is submitted, at the same point
  where the frontend list is refused today: an operation outside the surface is refused
  at submission, and so is one that could change the profile's records or reach the
  network when the surface is declared read-only or local. What search and describe
  reveal is not the enforcement. The test that shows this refusal runs over the
  surface's whole operation list at every Cadrumo release, because the list can grow
  under an unchanged name.
- Parity is defined and measured per registered operation, not per command or screen.
- Every registered operation is admitted on every frontend, MCP included, and the
  definition keeps no per-operation frontend list. A check fails when an operation the
  command line can submit is not submittable on MCP. (Amended 2026-10-12 under
  `2026-10-11-mcp-parity-full-parity-adr`; before that admission stayed opt-in per
  definition, each operation carrying a recorded MCP decision, admitted with the evidence
  of a checklist or excluded with a reason.)
- A surface's claim to be read-only or to stay on the machine is derived from what each
  operation on it can do, through the operation's own resolution of the request, and
  tested against it. (Amended 2026-10-12; before that it was derived from facts stated in
  each recorded MCP decision.)
- Parity is proved by an admission through the operation's real access resolver, not by
  reading a declared list, and no resolver compares the frontend.
- A safeguard that lives in a command handler or a screen moves into the operation, so
  that every frontend has it. (Amended 2026-10-12; before that it moved there before the
  operation it guards was admitted to MCP.)
- A capability the command line or terminal interface performs in process, and that an
  MCP client needs, becomes a registered operation or a sub-query of the public reference
  tool. It is not reached by a command-line call.
- Storage administration is served on MCP exactly as the command line serves it.
  (Amended 2026-10-12 under `2026-10-11-mcp-parity-full-parity-adr`; on 2026-10-10 the
  owner had said "Storage administration should not be an MCP responsibility", and the
  ruling of 2026-10-11 that MCP never refuses anything the command line can do replaced
  it.) Starting, stopping and supervising the runtime stays outside every frontend's
  operations, the command line's included.
- Fixed boundary, set by the owner and not open to any decision: nothing is designed,
  built or shipped that sends data to the tax authority and changes its state, and no
  support is given for doing so. The owner, 2026-10-10: "we won't build or ship code that
  sends data to and modifies the AEAT state". The check that records admission also
  asserts that no registered operation and no tool declares this, so the guarantee is
  tested as the registry grows. That assertion covers what definitions and tools declare.
  It does not show what code does, which is established by reading the code.

Hypotheses, free to change within the commitments above: the items of the admission
checklist; whether the recorded decision lives in a table beside the check or on the
definition; that the command-to-operation join used to map the packaged agent skills is
generated and not hand-written.

Affected prior rulings: the choice conforms to the accepted MCP purpose-authentication
record (`.vault/adr/2026-09-26-mcp-purpose-authentication-adr.md`) and needs no amendment
for the mechanism itself. How an MCP session
is authenticated is decided in
`2026-10-10-mcp-parity-shared-sign-in-door-adr`. Which operations are admitted,
and how an agent's write is authorised, are separate decisions not made here; both are
now made by `2026-10-11-mcp-parity-full-parity-adr`: every operation, with the same
authority as on the command line.

One sentence of the accepted agent-harness record needs an amendment the owner approves.
Its 2026-09-26 amendment says "The agent still sees a confined deterministic tool
universe, with no arbitrary code, SQL or shell capability"
(`.vault/adr/2026-07-02-agent-harness-refoundation-adr.md:254`). The owner ruled on
2026-10-10 that an assistant may hold Cadrumo's command line and Python as a door of its
own. Proposed wording: "Through the MCP server the agent sees a confined deterministic
tool universe: the server offers no arbitrary code, SQL or shell capability and performs
no work by invoking the command line. What an assistant does with a terminal of its own
is outside this record."

## Implementation

We will bring Cadrumo's MCP server to parity by deciding MCP admission per registered
operation and by repairing the generic tools, and we will not route any MCP work through
the command line.

- First, what is already open is made safe and usable: the unguarded sensitive
  operations, the definitions that list MCP and cannot run, unconfined host paths, and
  the discovery limits recorded in the defects reference.
- Then operations are admitted family by family, each through the checklist, with one
  contract cutover per family because the frontend set is part of the definition's
  contract digest. (Overtaken on 2026-10-11: under `2026-10-11-mcp-parity-full-parity-adr`
  every definition is submittable from every frontend and keeps no frontend list.)
- The order of families and the steps belong in a plan, not in this record.

## Rationale

The knockout is that the registry route is the only one consistent with Cadrumo's own
accepted rulings: every surface dispatches registered operations through the supervisor,
and a command-line wrapper for MCP was rejected by name. It also keeps the tool list
constant, which the consuming agent needs, and keeps authority where Cadrumo already
enforces it, in the runtime. Two independent reviews tried to break the mechanism and
could not; what they overturned was the authority model first attached to it, which this
record does not carry (`2026-10-10-mcp-parity-parity-mechanism-options-research`).

## Consequences

- One catalogue, one place where admission is decided, and a tool list a client can pin.
- Admission is work per definition: a disclosure check, and for a write the validations
  and guards the command line applies today.
- Each widening changes a contract digest and strands stored invocations of that
  definition, so cutovers are planned per family.
- The check that records decisions is new machinery; the existing catalogue test does not
  examine MCP.
- If the agent also holds Cadrumo's command line and Python, an MCP exclusion no longer
  limits what the agent can reach. It states what the typed, observable path offers.
- Reconsider if a live evaluation shows that models cannot drive search, describe and
  submit reliably; a small generated set of read tools would then be weighed. The owner
  has ruled that a first release ships the assistant's terminal and the tool path
  together ("No, both together",
  `2026-10-10-cadrumo-integration-owner-rulings-research`), so this work is not optional
  beside the command line.
- Accepted 2026-10-10 on the owner's advance authorization of that day: "if all findings
  converge we treat that as the approved state and continue onto plan writing". The three
  reviewing sessions the owner named agreed to this text, each within its scope: one read
  it against the consuming agent's code, one against the runtime, custody and native
  layer, and one against the accepted integration records from quoted passages.
  Acceptance records the decision. It is not evidence that any of it is built.
