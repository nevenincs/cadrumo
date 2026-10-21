---
tags:
  - '#adr'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-11'
body_schema: 'body-v2'
body_hash: 'sha256:28cbd7deca935b4452f99dcc8735139a8a1877354cb8717ee56e3b312aa91e9b'
related:
  - "[[2026-10-10-mcp-parity-replay-identity-reference]]"
  - "[[2026-10-10-mcp-parity-admission-rulings-adr]]"
  - "[[2026-10-10-mcp-parity-parity-mechanism-adr]]"
  - "[[2026-10-10-mcp-parity-approval-step-adr]]"
  - "[[2026-10-10-mcp-parity-admitted-surface-defects-reference]]"
  - "[[2026-06-30-ledger-add-idempotency-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
---

# `mcp-parity` adr: `An agent's effectful submission carries the caller's own replay identity, and a key answers only while its operation could have changed something` | (**status:** `rejected`)

Rejected on 2026-10-11. The owner ruled first-hand that the command line, the terminal interface and MCP are at parity and that MCP never refuses anything the command line can do: "MCP should aboslutely NEVER refuse anyhting the cli can do" and "I want the cli tui and mcp to be partify. clic can do everythign so should the tui and mcp. no more qesitons". This record made the admission of operations wait on a mechanism, which `2026-10-11-mcp-parity-full-parity-adr` rules out. It is kept as history.

## Problem Statement

An MCP client or a hosted assistant retries when a reply is lost or a turn is repeated. The `execute` tool accepts a key and nothing requires one. A keyless retry of a write runs twice. A keyed retry returns the first operation whatever became of it, so a first attempt that was refused answers every later retry with that refusal. The ledger writes the owner admitted to agents cannot open until both are settled.

## Considerations

Code facts are in `2026-10-10-mcp-parity-replay-identity-reference`.

- The accepted `2026-06-30-ledger-add-idempotency-adr` chose a caller-supplied key and rejected content-derived identity, because two identical movements on one day must both be recordable.
- That record relies on a written instruction to make an agent pass the key. It names the keyless agent call as the way the double write reopens.
- The claim mechanism already exists for every definition. It binds definition, subject, key and the exact request.
- Resolution never reads the outcome of the earlier operation, although the journal holds it.
- A reply to a replay cannot be told from a fresh admission.
- The runtime already knows, at submission, whether a request can commit.
- Key sessions last at most five minutes (`2026-10-10-mcp-parity-admitted-surface-defects-reference`, section 9). A retry often arrives on a new session.
- The proposed `2026-10-10-mcp-parity-approval-step-adr` consumes an approval before admission and says a replay that resolves to an admitted operation needs none.
- The command line sets no wire key. A hosted assistant can run the same writes through it.

## Considered options

- **Accept keyless submissions as appends that cannot be replayed.** Simple, and right for a person. Rejected for agent callers: an unattended caller retries, and each retry would write again.
- **Derive the key from the request content.** No caller change. Rejected, as the accepted record rejected it. Two identical legitimate acts collapse into one. Archive, restore, archive fails: the third act has the content of the first and would return the first. Only a time window would separate them, and a window makes a late retry write twice.
- **Have Cadrumo mint a key per submission.** Rejected: a caller that lost the reply never learns the key, so it is a keyless append with extra steps.
- **Require a key by the definition's declared replay policy, or by the per-definition fact that it can change records.** Rejected as the test: the declared policy is not consulted at submission and some definitions that can update declare none; the per-definition fact would demand a key for a preview.
- **Require the caller's key on any submission that can commit, refuse without it, and let a key answer only while its operation is unsettled or may have changed something.** Chosen.

## Constraints

Binding:

1. **Refusal without a key.** A submission from a gated caller that can commit is refused when it carries no key. A gated caller is the one `2026-10-10-mcp-parity-approval-step-adr` defines: a connection that declares the MCP frontend, or a peer inside a hosted assistant's process tree. "Can commit" means the operation's own access resolution of that exact request grants the commit action. The runtime refuses at submission, before anything is stored, journaled or leased, with a definite code distinct from `unresolved`.
2. **Who supplies it.** The host that owns the turn, through the existing key argument. One key names one intended act. A retry of that act reuses the key. A new act takes a new key. Cadrumo never derives a key from content, time or the request, and never mints one for the caller. Two identical legitimate acts are two keys.
3. **Scope.** A claim is scoped to the profile, the definition, the subject and the key. It is not scoped to a session or a frontend, so a retry after a reconnect, or through the other door, resolves. A claim never resolves across profiles.
4. **What a replay returns.** While the earlier operation is unsettled, that operation is returned and nothing new is admitted. When it settled with an applied or partial effect, that operation is returned and never runs again. When it settled with an unknown effect, that operation is returned and never runs again; the caller reconciles by reading state, and a later attempt is a new act with a new key. When it settled with no effect, whether it succeeded as a no-op, was refused, failed or was cancelled, the key is released and the submission is admitted as a new operation.
5. **Request binding.** While a claim answers, the same key with a different request is refused. A released key is free, so a corrected request under the same key is admitted.
6. **A replay is visible.** The reply to a replay says it is one and carries the earlier operation's lifecycle, terminal condition and effect. A replay starts nothing and does not revive a response capability.
7. **Lifetime.** A claim has no time expiry. It lives as long as the journal record of its operation. Any later decision to remove journal records must state what happens to their keys.
8. **Wire key and payload key.** The wire key decides whether an operation is admitted. A payload key that names a record, such as the one on `ledger.add`, decides whether that record is created, and `2026-06-30-ledger-add-idempotency-adr` still governs it. They are layers, and neither overrides the other. A gated caller must supply the record key where the definition has one, because a new wire key after an unknown outcome would otherwise append a duplicate.
9. **Order with the approval step.** The key check comes first, then claim resolution, then the approval gate. A replay that resolves returns its operation and neither needs nor consumes an approval. While an approval waits, no operation exists and no claim is written. A released key on a reserved act is a new submission and needs a new approval.
10. **The command line.** The same rule holds for a gated caller on the command line. The command line gains one way to carry the caller's key to the wire. Until the runtime can recognise the assistant's process tree, the rule binds the MCP frontend only.
11. **A person's own session.** Unchanged. A keyless submission from the person's terminal or terminal interface stays an append.
12. **Honest declarations.** A definition admitted to the MCP frontend that can commit does not declare its replay policy as none. Its executor records an effect other than none before its first write. Both are items of the admission checklist, because the release rule depends on the second.

Hypotheses, free to change within the commitments:

- The key check sits beside the existing commit-scope refusal in access evaluation.
- Resolution reads the lifecycle and effect of the matched journal record to decide whether the claim answers.
- The profile is added to the claim digest, unless the journal root is shown to be per profile.
- The command line carries the key as one global option, and adds an ordinal per submission when a command submits several operations.
- The record key may default to the wire key when the caller sends none. It is still the caller's identity.
- The names of the new reply fields and of the refusal code.

Left open, to be ruled when it is built: what a caller can do with a replayed operation that was admitted and never started, when its submitting session is gone. It must become startable by the key's holder or be settled.

To confirm with the owner: that the person's own terminal and terminal interface keep accepting writes with no key; that a key never expires, so an agent that reuses an old key by mistake gets the old operation back, marked as a replay; and that the rule covers every MCP client, the same set the approval step gates.

Affected prior rulings, each needing an amendment the owner approves, are listed under Consequences.

## Implementation

We will require a caller-supplied key on every submission from a gated caller that can commit, and we will make a key answer only while its operation is unsettled or may have changed something.

- The runtime refuses the keyless submission at admission and reports it as a definite outcome.
- Claim resolution reads the outcome of the earlier operation and releases a key whose operation settled with no effect.
- The submission reply marks a replay and carries its state. The `execute` tool passes that through.
- The admission checklist gains the two items of constraint 12.
- The command line gains the key pass-through. The packaged agent material states one key per intended act.

## Rationale

The caller is the only party that knows whether two identical requests are one act or two. The accepted ledger-add record reached that conclusion for one command, and this record applies it to every effectful operation an agent submits. Enforcing it in the runtime replaces a written instruction that the earlier record called load-bearing. Reading the outcome on resolution removes the permanent refusal without re-running anything that may have changed records. Using the existing commit test keeps one definition of effectful at the submission door.

## Consequences

- A retry after a lost reply is safe: the same request under the same key returns the operation or admits it once.
- Archive, restore, archive all take effect, because each act has its own key.
- A host that reuses a key for a new act gets the old operation back. The replay marker shows it. Cadrumo cannot detect the mistake.
- A model that sends no key has its write refused and nothing changes.
- Some reads resolve commit because signing in may save a provider session. They will need a key from an agent. That is safe and costs the caller one argument.
- Resolution scans every journal file. The journal is unbounded by design, so the cost grows with use.
- Adding the profile to the claim digest strands existing claims. Only test data exists.
- Amendments required once this record is accepted:
  - `2026-08-11-tui-architecture-adr`, line 560. "`submit` accepts an idempotency key scoped to the definition and subject; replay returns the existing invocation" becomes "`submit` accepts an idempotency key scoped to the profile, the definition and the subject. Replay returns the existing invocation while it is unsettled or settled with an applied, partial or unknown effect. A key whose invocation settled with no effect is released. `2026-10-10-mcp-parity-replay-identity-adr` states when a key is required".
  - `2026-06-30-ledger-add-idempotency-adr`, Implementation. Its sentence that the keyless path stays a non-idempotent append gains "A caller that `2026-10-10-mcp-parity-replay-identity-adr` treats as an agent is refused a keyless add by the runtime. It records two identical movements with two keys". Its sentence that the agent harness contract requires the agent to pass a stable key becomes "The runtime requires the key from an agent caller under `2026-10-10-mcp-parity-replay-identity-adr`. The agent harness contract states the same rule and is no longer the only safeguard".
  - The proposed `2026-10-10-mcp-parity-approval-step-adr`, constraint 10, is edited and not amended, since it is not accepted. "A replay under the caller's key that resolves to an operation already admitted returns that operation, and neither needs nor consumes an approval" becomes "A replay under the caller's key that resolves to an operation already admitted, and not settled without effect, returns that operation, and neither needs nor consumes an approval. Resolution runs before the approval gate. A key released under `2026-10-10-mcp-parity-replay-identity-adr` is a new submission and needs a new approval".
- Reconsider if a live run shows models reuse keys across acts, if journal scan time becomes material, or if journal records start to be removed.
