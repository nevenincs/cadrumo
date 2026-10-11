---
tags:
  - "#adr"
  - "#mcp-parity"
date: '2026-10-11'
related:
  - "[[2026-10-10-mcp-parity-closed-operations-reference]]"
  - "[[2026-10-10-mcp-parity-surfaces-and-registry-reference]]"
  - "[[2026-10-10-mcp-parity-parity-mechanism-adr]]"
  - '[[2026-07-08-mcp-protocol-hardening-adr]]'
supersedes:
  - '2026-10-10-mcp-parity-admission-rulings-adr'
modified: '2026-10-11'
body_schema: 'body-v2'
body_hash: 'sha256:631daf563ae7966f2218f839955f0f97c797951f6c746681311c4aaedbcd51ff'
---

# `mcp-parity` adr: `The command line, the terminal interface and MCP are at parity, and no frontend is refused what another can do` | (**status:** `accepted`)

## Problem Statement

The work to make the MCP server a full interface was built on a wrong reading of the owner's rule. The owner had said that an agent has full control over the person's data and operations and that the person approves sensitive operations. That was read as licence to refuse a sensitive operation on MCP until an approval step exists. Each review then added refusals: sensitive variants, a guard on rows the person classified, results reduced for an agent, results unreadable across frontends. On 2026-10-11 the registry held 270 operations, 105 of which the command line could submit and MCP could not, and many more behaved differently on MCP. The owner rejected this outright.

## Considerations

- The owner's ruling, first-hand and verbatim, on 2026-10-11: "MCP should aboslutely NEVER refuse anyhting the cli can do. stop underminig the program". "I don't want to list out all the feautre you're redneirng impossible to use. the mcp is tool for the agent to pea[ret the carumo application. not q suerface to stifle". "I'm not going to aswer 16 questions and it is already crystal clear what I want, I want the cli tui and mcp to be partify. clic can do everythign so should the tui and mcp. no more qesitons".
- The owner's earlier ruling, 2026-10-10: "all ledger ops must ne possible to ne opersted by the agents ... agent generslly spealijg shouod have full control ovet ht user data and ops."
- A refusal the command line does not have makes a feature unusable for an agent. "Wait for a step that is not built" is a refusal.
- The frontend a client declares is a client claim the runtime cannot verify, and the hosted assistant can run the command line itself. A rule that differs by frontend limits only the honest path.
- Cadrumo never submits, files, signs or writes anything to the tax agency, on any frontend. Parity does not touch that, because no frontend can do it.

## Considered options

- **Parity with no frontend-specific refusal.** Chosen. It is what the owner ruled.
- **Parity except for operations ruled sensitive, held until an approval step exists.** Rejected by the owner. It was the state of the work on 2026-10-11.
- **Parity of operations with reduced results for an agent.** Rejected under the same ruling: a result withheld from an agent is a feature the agent cannot use.

## Constraints

Binding:

1. Every registered operation the command line can submit can be submitted from the terminal interface and from MCP.
2. No access resolver, executor, action, guard or runtime check refuses, narrows or changes what an operation does because of the frontend that submitted it. The same request gets the same decision and the same effect on every frontend.
3. A result is the same on every frontend. A session reads on MCP whatever it could read on the command line.
4. Where MCP lacked a way to carry something the command line carries, a typed secret, an answer to an interaction, a host file path, MCP is given that way. The operation is not refused.
5. No operation is held back from a frontend for being sensitive, destructive, an election, an attestation, a local filing act, a file input or output, or for want of an approval step, a file-exchange folder, a replay identity or a provenance mark.
6. What remains is the same on every frontend: input validation, profile and subject checks, the finalised-revision guard, handle-level path checks, the session's lease and scope, and the surface a person may choose to narrow when starting the MCP server. The default surface is everything.
7. Attribution is not a limit: an execution admitted on MCP records an actor derived from its session, and a row records whose decision its classification is. No refusal is built on either.
8. Good conduct for an agent, such as telling the person before a destructive act, is guidance in the packaged agent text. It is never a product gate.

Fixed boundary, not open to any decision: nothing on any frontend sends anything to the tax agency. Export writes a local file and the filed marker writes a local record.

Affected prior rulings:

- `2026-10-10-mcp-parity-admission-rulings-adr` is superseded by this record. Its rule of judgement, its family table, its exclusions and every later row added to it no longer apply.
- `2026-10-10-mcp-parity-approval-step-adr`, `2026-10-10-mcp-parity-file-exchange-adr`, `2026-10-10-mcp-parity-replay-identity-adr` and `2026-10-10-mcp-parity-agent-provenance-adr` were proposed and never accepted. They are rejected: each made admission of operations wait on a mechanism, which constraint 5 rules out.
- `2026-10-10-mcp-parity-shared-sign-in-door-adr` stays accepted for how an MCP connection obtains a session. Two of its lines yield to constraint 2: that a session on the MCP frontend may end only itself, and that the runtime refuses on the MCP frontend what it admits on the command line for a session of the same kind. A session of the human kind does on MCP what it does on the command line.
- `2026-10-10-mcp-parity-parity-mechanism-adr` stays accepted: parity is reached through the operation registry and the generic tools.
- `2026-07-08-mcp-protocol-hardening-adr` stays accepted. One sentence of its ruling H8 yields to constraint 2: that no secret ever rides any MCP channel. The command line takes a typed secret from the person, so an MCP connection carries one too, from the tool call to the runtime's protected frame. What H8 decided about the protocol's own credential elicitation is untouched: Cadrumo still does not use it. H8's purpose, that a secret need not pass through a model, is served by adding a form and removing none: a secret the person stores at a terminal of their own and the tool call names by reference, beside the typed argument. Its ruling H9 on the SDK version was already replaced by `2026-07-31-mcp-sdk-major-carry-adr`.

## Implementation

We will make every definition submittable from every frontend, remove every frontend-specific refusal and result difference from resolvers, executors, guards and the runtime's release of results, give the MCP harness the means to carry a typed secret and to answer every interaction kind, and replace the tests that held rulings with tests that hold parity: every operation on every frontend, the same resolver decision for the same request, and no comparison of a frontend inside an access path outside a short allow-list.

Hypotheses, free to change within the constraints: whether the definition keeps a per-operation list of frontends at all; the form of the tool argument that carries a secret; whether session acts get tools of their own.

As built by 2026-10-12, recorded here as implementation and not as commitments of this record. A change to any of them that keeps the constraints needs no new decision; one that others must build on is a decision for a record of its own.

- Work that needs no profile is served to the terminal interface and MCP by a sessionless family of runtime requests, the installation acts, admitted on the verified connection the way profile deletion is. The command line keeps doing that work in its own process and uses the acts only where the runtime must act first, as for the reset of all profiles while the runtime hosts one.
- A contained profile worker asks the runtime to start the model reader's server, under the commit fence of the provisioning operation and for that operation only. The instruction names no program and no environment.
- On MCP a secret can be named by reference. The reference names a record of its own kind in this machine's protected credential store: one a person entered at a terminal, or a recovery code held for the person to read. A typed secret argument stays.
- Operations are discoverable on MCP with no session and no runtime from a generated copy of the public contract set shipped with the tool server and held to the registry by a test.
- The definition keeps no per-operation list of frontends. Session acts have a tool of their own, and so do the installation acts.
- The default MCP surface is named `full`. A surface name is pinned to its tool list by a test, so that a consumer that mounts the tool server by name and tool list is told when the list changes.

## Rationale

The owner ruled it, twice, in terms that leave no exception. The earlier reading produced a server that could not do what the command line does, which defeats the purpose of the feature: an agent operating the application.

## Consequences

- An agent can remove, reset, merge, export, record the filed marker, amend, import and classify exactly as the command line can, with no approval gate in the product.
- The safeguards that remain for those acts are the ones the command line has inside the operations, and the agent's own conduct as its packaged rules describe it.
- The refusals, reduced results and their tests built between 2026-10-10 and 2026-10-11 are removed. The review findings that motivated them, recorded in `2026-10-11-mcp-parity-audit`, are closed as not applicable under this record, except those about defects on every frontend.
