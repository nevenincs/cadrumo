---
tags:
  - '#adr'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-11'
body_schema: 'body-v2'
body_hash: 'sha256:c8259241f1787b5213d4f7be7d3f2f4cccbee056fb7e59789528183e624ac038'
related:
  - "[[2026-10-10-mcp-parity-approval-step-reference]]"
  - "[[2026-10-10-mcp-parity-admission-rulings-adr]]"
  - "[[2026-10-10-mcp-parity-shared-sign-in-door-adr]]"
  - "[[2026-10-10-mcp-parity-parity-mechanism-adr]]"
  - "[[2026-10-10-mcp-parity-admitted-surface-defects-reference]]"
  - "[[2026-10-10-mcp-parity-sign-in-doors-reference]]"
  - "[[2026-10-04-application-sign-in-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-04-runtime-manager-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-adr]]"
  - "[[2026-09-26-mcp-purpose-authentication-profile-access-adr]]"
---

# `mcp-parity` adr: `The person approves a reserved act in Cadrumo before it is admitted, through a single-use runtime approval bound to the exact request` | (**status:** `rejected`)

Rejected on 2026-10-11. The owner ruled first-hand that the command line, the terminal interface and MCP are at parity and that MCP never refuses anything the command line can do: "MCP should aboslutely NEVER refuse anyhting the cli can do" and "I want the cli tui and mcp to be partify. clic can do everythign so should the tui and mcp. no more qesitons". This record made the admission of operations wait on a mechanism, which `2026-10-11-mcp-parity-full-parity-adr` rules out. It is kept as history.

## Problem Statement

The owner has ruled that an agent has full control over the person's data and operations, and that the person approves sensitive acts: each time, for the exact act, in a step taken in Cadrumo and enforced by Cadrumo's runtime. No such step exists. Every sensitive operation is refused on the MCP frontend until it does, and the hosted assistant's terminal cannot ship without it. This record decides the step: where it is shown, what it binds, how it attaches to both doors, how the runtime recognises who is asking, and what the reserved set is.

Records named `2026-10-10-cadrumo-integration-...` belong to the vault of the cadrumo-agent repository, a separate project that drives this application; they are cited by name and are not in this vault.

## Considerations

Code facts are in `2026-10-10-mcp-parity-approval-step-reference`.

- A review's answer belongs to the session that submitted the operation, and the MCP `respond` tool answers from that session. As built, an agent would approve its own act.
- The accepted `2026-10-10-cadrumo-integration-terminal-access-adr`, confirmed by the owner, fixes the command-line behaviour: a reserved command runs nothing, returns at once, and runs only when the identical command is issued again after approval. Nothing blocks waiting for a person.
- The consuming agent makes no decision per call and never repeats a turn. A step that pauses the caller does not fit an unattended run.
- An operation that waits after admission holds its subject. A second submission of the same definition and subject is refused while it is unsettled (`2026-10-10-mcp-parity-admitted-surface-defects-reference`, section 6).
- The runtime has the peer's process id and a retained handle. It has no ancestry. The frontend is declared by the client and cannot be verified (`.vault/adr/2026-10-04-application-sign-in-adr.md:94`).
- A call through the relay reaches the runtime from the Cadrumo process serving the surface, which is outside the assistant's process tree.
- The desktop shell holds no runtime connection. It already drives sign-in through dedicated host commands that run the canonical command line.
- The command line marks commands `destructive` or `handoff`. Neither flag matches the rulings: `modelo reconcile import` is marked hand-off and the owner ruled it free, and elections, consents and account changes carry neither flag.
- An existing policy field, `transaction_authority_required`, refuses with its own code and is set by nothing.
- The owner, first-hand on 2026-10-10: "Agent generally speaking should have full control over the user data and ops. User will be required to approve sensitive ops."

## Considered options

- **The existing review interaction, unchanged.** No new machinery. Rejected: the submitting session holds the answer, so the agent approves itself.
- **A new interaction kind answered by another session.** The operation is admitted, pauses, and a person's surface answers. Rejected: a command would block, or leave an admitted operation that its identical re-issue collides with; the waiting operation holds its subject with no person guaranteed to come; and it reverses the accepted rule that another process cannot obtain response authority. It also needs a change in every reserved executor.
- **An approval kept by the desktop host and asserted to the runtime.** Rejected: the runtime would enforce a claim, and the shell would gain authority it is ruled not to hold.
- **An MCP elicitation or a client confirmation.** Already ruled out by the owner and by the amended agent-harness record.
- **An approval record kept by the runtime, asked for and consumed before admission, the same for both doors.** Chosen.

## Constraints

Binding:

1. **One mechanism.** A reserved act asked for by a gated caller is refused at submission and admits nothing. The runtime records a pending approval. The act runs only when the person has approved that record and the caller submits the identical request again. This holds for an operation submitted through MCP and for a command or script that reaches the runtime from the assistant's terminal.
2. **Who is gated.** A caller is gated when either holds: its connection declares the MCP frontend, or its peer process is inside a hosted assistant's process tree, whatever frontend it declares. Tree membership is read by the runtime from operating-system evidence about the peer it authenticated. No field the caller sends can clear it. When the evidence cannot be read, the caller is treated as gated. On a platform where the runtime cannot identify the tree, the assistant's terminal is not offered.
3. **The relay.** The Cadrumo process that serves a hosted assistant's surface connects on the MCP frontend, so its calls are gated without being recognised. It marks its connection as serving the hosted assistant. The mark only labels and restricts; nothing is granted by it.
4. **What an approval binds.** The runtime boot, the exact profile, the profile's sign-in generation, the definition and its contract digest, the subject, the digest of the validated request, the pinned authority generation, the requester as the runtime identifies it, and two expiry instants. The requester is the grant for a key session, the session for an MCP client under the sign-in, or the assistant's tree for a command or script. Where a definition declares a baseline, the approval binds it; a changed baseline consumes nothing and asks again.
5. **Single use.** An approval is consumed before the operation is admitted. A failure after consumption costs a new approval and never a second run. An approval is never extended.
6. **Shown with the exact act.** The person sees, rendered by Cadrumo from the bound facts: who asks, the profile, the operation and why it is reserved, the subject in a form a person recognises, every request field with its full value, and the expiry. Nothing the caller wrote is presented as the act. The answer names the record and the digest the surface displayed, and the runtime refuses an answer whose digest differs.
7. **Where it is answered.** In the desktop window and in the terminal interface. The command line has the canonical leaves to list and answer, and the desktop uses them through dedicated token-checked host commands, as it does for sign-in. The shell still holds no session and no connection. The shown act stays in memory only on every surface.
8. **Who may answer.** A human-kind session from the shared sign-in for that exact profile, on the terminal interface or the command line, with an active unlocked OS login, whose peer is outside every assistant tree. The answer is not a registered operation and is not reachable from the MCP tools. A key session, an attended session and a connection on the MCP frontend can never answer.
9. **Nobody signed in.** A key session may ask. With no live sign-in for the profile the request is refused as unavailable and nothing is recorded. An approval is never given without a signed-in person.
10. **States.** While an approval waits, no operation exists: nothing is journaled, leased or started. The caller receives a definite reply that nothing was admitted, distinct from the `unresolved` outcome, which distinguishes waiting, declined, expired and no person signed in. Decline runs nothing and is remembered, so the same request raises no new prompt while that record lives. Sign-out, lock, the sign-in deadline and a runtime restart drop every pending and unused approval of the profile. When a hosted run ends, the Cadrumo process serving the assistant withdraws that run's pending and unused approvals, so an approval answered after the run ended is never used by a later run. The same request submitted again while it waits returns the same record. After consumption the next identical request needs a new approval. A replay under the caller's key that resolves to an operation already admitted, and not settled without effect, returns that operation, and neither needs nor consumes an approval. Resolution runs before the approval gate. A key released under the proposed `2026-10-10-mcp-parity-replay-identity-adr` is a new submission and needs a new approval. Once admitted, the operation settles under the supervisor's rules, and an ambiguous outcome stays `UNKNOWN` or `SETTLING`.
11. **Other doors to the same act.** A gated caller cannot resume a reserved operation unless it was admitted on an approval given to that requester.
12. **Record of use.** The admitted operation's provenance records the approval it consumed: its identifier, digest, the answering session and the time. A pending request is never written to disk.
13. **The reserved set.** It is declared once, per registered operation, and published in the operation's public contract. Its content is the classification of `2026-10-10-mcp-parity-admission-rulings-adr`: the operations that record admits behind the person's approval. The command line's set is derived from it through the generated join of commands to operations, and published in the command-surface manifest, which says of each command whether it waits for approval or is refused outright. The `destructive` and `handoff` flags stay as descriptions, and a check fails when a flagged command is neither reserved nor a recorded exception. `modelo.reconcile.import` is a recorded exception by the owner's ruling, and any other flagged command the rulings record admits without approval is recorded the same way. The reversible ledger lifecycle operations are not reserved on either door.
14. **Person-only commands.** Commands that change state with no session, start other programs, download or install components, or administer access or the machine are refused by the command line inside the assistant's tree, with no approval path. That refusal is the command line's own; a script that calls internals directly is not held by it, as the terminal-access record states.
15. **Bounded.** The number of pending approvals per profile is bounded, and a request beyond the bound is refused.
16. **What this is not.** The step limits the hosted assistant and any client that declares MCP. It is not a barrier against other code running as the same account, which the owner has ruled is not a security concern. A process that a script has a system service start is outside the assistant's tree, and the tree test does not catch it.

Fixed boundary, not open to any decision: no reserved act, approved or not, sends anything to the tax authority. `modelo.export` writes a local file and `modelo.work.file` writes a local record.

Hypotheses, free to change within the commitments:

- The gate sits at the SUBMIT guard and reuses `transaction_authority_required` and its refusal code.
- The record lives in the runtime parent or the profile worker.
- The assistant's tree is a named Job Object on Windows that the runtime opens and tests the retained peer handle against.
- A pending request waits ten minutes and an approval stays usable for two.
- Each reserved definition may register a presenter for its act; a field table is the floor.
- Access evaluation learns the intent of a review response. Today apply, reject and inspect evaluate as one access action, so an apply cannot be refused or gated without refusing a reject; an optional response intent on the access context would separate them.
- A command that submits more than one reserved operation gets one grouped approval.
- A person's answer counts as that person's activity once the idle extension is built.
- The desktop's command-line children use the same explicit option to use the stored sign-in that a command run without a console needs.

To confirm with the owner, because each changes a binding line if answered otherwise: that the desktop window may show and answer approvals as well as the terminal interface (line 7); that the person-only commands have no approval path in the assistant's terminal, which is stricter for those commands than "Assistant, after asking each time" (line 14); that seeing and approving the elections and the bank account the assistant proposed is enough for an export or a local filed record, without the person entering them; that an editor's MCP client and an agent on an enrolled key get the same step as the hosted assistant (line 2); and the two waiting times.

Affected prior rulings, each needing an amendment the owner approves. The wording is listed under Consequences.

## Implementation

We will add a runtime-held, single-use approval that a gated caller must obtain before a reserved operation is admitted, answered by the signed-in person in the desktop window or the terminal interface.

- The runtime gains the reserved attribute on definitions, the gate, the approval records and two requests: list and answer.
- The runtime learns to test a peer against the hosted assistant's process tree. The process that hosts the assistant gives that tree an identity the runtime and the command line can check.
- The command line gains the list and answer leaves, the person-only refusal inside the tree, and the reservation in its manifest.
- The desktop gains a pending-approvals surface and its host commands. The terminal interface gains the same surface in its own session.
- The MCP `execute` tool reports the new refusals as definite outcomes.

## Rationale

The knockout is the command-line door. The owner confirmed that a reserved command runs nothing and returns at once, and that the identical command runs after approval. Only an approval taken before admission behaves that way, and using it for MCP gives one mechanism, one reserved set and one enforcement point in the runtime. It also covers a script that goes through the runtime, as the owner ruled. Because nothing is admitted while the person decides, there is no waiting operation to expire, to hold a subject, or to be left unanswerable when the sign-in ends. Gating every MCP connection removes the need to prove who is behind the relay. Tree recognition is then needed only where the frontend says command line.

## Consequences

- Every sensitive operation can be admitted to MCP behind this step, and the hosted assistant's terminal can ship with reserved commands held.
- A person's own MCP client, such as an editor, is gated like the assistant. That follows from the owner's rule.
- The agent has to submit twice for a reserved act. A model that does not re-issue the request leaves the act undone, which is the safe failure.
- The approval binds the request, not a preview of its effect. Where a reserved operation also pauses in a review that is itself the person's decision, its admission folds that decision into what the approval shows, or keeps the review's answer away from the agent. That is settled per operation as each is admitted.
- The desktop shell gains its first surface that answers something other than sign-in. Its rule of no connection and no session is kept.
- An approval needs a signed-in person, and a key session can still ask. The reserved operations can therefore be proved on the key route before the shared sign-in door opens; the hosted assistant's route needs that door.
- Tree recognition does not exist in code, and neither does the assistant's host. Both are new work, and the Windows mechanism is a hypothesis until built.
- Two sentences of the cadrumo-agent records read differently under this record and were relayed to that project: the runtime, not the host, holds the pending request, in memory only, which that project accepts as the same in substance; and the person-only commands have no approval path, which is the owner's to rule. Its requirement that an approval given after a turn has ended is never used is met by the withdrawal in line 10. On 2026-10-10 the owner ruled on this first-hand in that project, relayed by its integration session: asked whether the short expiry was enough, the owner kept the rule and chose "Cadrumo withdraws the assistant's pending requests when a run ends, so an approval can only ever serve the run that asked." The withdrawal in line 10 is therefore a requirement by ruling, and the expiry times are not what guarantees it.
- Amendments required once this record is accepted:
  - `2026-10-04-runtime-manager-architecture-adr`, line 109. "Approval prompts belong to the TUI. Application sign-in follows `2026-10-04-application-sign-in-adr`; the manager hosts neither" becomes "Approval prompts belong to the TUI, except the approval of a reserved act asked for by an agent, which `2026-10-10-mcp-parity-approval-step-adr` places in the desktop window and the TUI. Application sign-in follows `2026-10-04-application-sign-in-adr`; the manager hosts neither".
  - The same record, line 314. "Approval prompts belong to the TUI" gains "with the exception stated under Authority".
  - The same record, line 321. The follow-on decision "How MCP-originated approval requests are surfaced when no TUI is open" gains "decided in `2026-10-10-mcp-parity-approval-step-adr`: they are held by the runtime and answered in the desktop window or the TUI".
  - `2026-10-04-desktop-shell-adr`, line 93. "approval prompts still belong to the TUI" becomes "Approval prompts still belong to the TUI, except the approval of a reserved act under `2026-10-10-mcp-parity-approval-step-adr`, which the shell shows and answers only through dedicated token-checked host commands that run the canonical CLI".
  - The same record, line 82. The list of exceptions gains "the pending approvals of the signed-in profile and the person's answer to each, read and sent through dedicated host commands to the canonical CLI and held in memory only".
  - `2026-08-11-tui-architecture-adr`, D4, line 481. "Approval is a specialized interaction. It binds the exact request, baseline, reviewed proposal, proposed effect digest, actor, and time" becomes "Approval of a proposal that a running operation produced is a specialized interaction. It binds the exact request, baseline, reviewed proposal, proposed effect digest, actor, and time. The person's approval of a reserved act that an agent asks for is taken before admission under `2026-10-10-mcp-parity-approval-step-adr`, and binds the exact request, the baseline where the definition declares one, the answering actor and the time".
  - `2026-10-10-mcp-parity-admission-rulings-adr`. "How that step reaches an operation submitted through MCP is not designed here" becomes "How that step reaches an operation submitted through MCP is decided in `2026-10-10-mcp-parity-approval-step-adr`". "Whether the reversible lifecycle operations ... belong in the command line's reserved set is decided where that set is defined" becomes "The reversible lifecycle operations, which hide a record without removing it, are not in the command line's reserved set".
  - `2026-10-10-mcp-parity-shared-sign-in-door-adr`, Hypotheses. "so that process has to carry the fact forward. How it does so is designed with the approval step" becomes "so that process marks its runtime connection as serving the hosted assistant. The mark only labels and restricts, and the approval gate on the MCP frontend does not depend on it".
  - `2026-09-26-mcp-purpose-authentication-profile-access-adr`, capability matrix, gains a row: activity "Approve a reserved act an agent asks for"; required authority "A live human sign-in for the exact profile on the TUI or CLI, outside the assistant's process tree; no fresh password"; what it establishes "One use of that exact act, ending with the sign-in".
- Reconsider if a reserved act needs the person to enter a value and not only to approve one, if tree recognition cannot be built on a platform that must ship the terminal, or if a live run shows models do not re-issue an approved request.
