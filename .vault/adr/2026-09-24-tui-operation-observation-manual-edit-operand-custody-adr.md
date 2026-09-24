---
tags:
  - '#adr'
  - '#tui-operation-observation'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:059c461961a60fa5cb8339474cfe3be0935667395f120c30fb56d4e3a8937614'
related:
  - "[[2026-08-24-tui-operation-observation-adr]]"
  - "[[2026-08-27-tui-architecture-credential-free-type-aware-gate-adr]]"
  - '[[2026-09-24-tui-operation-observation-manual-edit-operand-custody-reference]]'
---

# `tui-operation-observation` adr: `complete operand custody for manual edit values` | (**status:** `proposed`)

## Problem Statement

The accepted operation-observation decision designs how manual financial edit
values reach an operation. Its amendment to D3a, D4, D5 and D6 introduces
transient financial operand custody for exactly that case. A Modelo edit
submits its typed operand through a runtime-only grant. The supervisor holds
the value only in memory for the exact requirement, the registered executor
consumes it once, and the value is never serialized, journalled or stored
(`2026-08-24-tui-operation-observation-adr`).

That design was declared but never completed
(`2026-09-24-tui-operation-observation-manual-edit-operand-custody-reference`).
The Modelo edit-apply definition declared the manual-override operand, but its
executor never took the value through the operand broker. The amount travelled
inside the operation request, which was journalled as plain JSON, and the
declaration was used only for its bounds check. Commit `01b78c1021`
(2026-09-22) then moved the edit-apply request to encrypted secure-reference
storage and removed the operand declaration, and a conformance test now pins
that policy. As a result:

- manual edit values are persisted, encrypted, as part of the stored request.
  That is safer than the plain journal it replaced, but the accepted design
  never persists them at all;
- the accepted credential-free gate decision specifically considered and
  rejected secure-reference storage for this request, because it would set
  the pattern for a reason unrelated to storage risk
  (`2026-08-27-tui-architecture-credential-free-type-aware-gate-adr`);
- the transient operand protocol now has no production consumer, and its
  composition proofs had to be moved onto a test-only definition to keep
  exercising the custody guard.

The commit records no rationale for the change. Either the accepted design is
completed, or the change is ratified by amending both decisions.

## Considerations

- Transient custody is strictly stronger for the values it covers. Nothing
  about the value survives the operation, so neither a journal, a backup nor a
  secure store can leak it later. Secure-reference storage is encrypted at
  rest but durable.
- Both designs meet the project rule that private financial payloads use
  approved encrypted persistence only. Transient custody meets it by never
  persisting the value; secure-reference storage meets it by encrypting what it
  persists.
- The operand protocol, its custody checkpoints, its crash classification and
  its composition guard are implemented and tested. Retiring them removes an
  accepted capability whose only consumer was taken away without a decision.
- Restoring the consumer reverses a shipped change and its conformance pin, so
  it needs the same care as any contract change: the request schema and the
  stored-request policy move back together, and requests stored by the
  intermediate version must be handled.

## Considered options

- **Complete the accepted design (recommended).** The edit-apply definition
  declares the manual-override operand again, and its executor takes the value
  through the operand broker it now has access to. Its request returns to the
  credential-free journal and carries no manual values, and those values travel
  only through operand custody. The intermediate secure-reference policy and
  its conformance pin are removed together.
- **Ratify secure-reference storage and retire the protocol.** Amend the
  observation decision to withdraw transient operand custody, amend the
  credential-free gate decision's rejection, and delete the protocol with its
  custody store, submission path and composition guard. This is simpler, but
  weaker for the values concerned, and it discards a finished capability.
- **Keep both as they are.** Rejected. It leaves an accepted design and the
  shipped code in contradiction, and keeps a guarded capability alive only
  under test.

## Constraints

- Operation request schemas are versioned public contracts. Changing the
  edit-apply request back is a new schema version, not an in-place edit.
- Requests persisted under secure-reference storage by the intermediate version
  must either be settled before the change or refused with a typed, localized
  reason. They must never be read as the restored shape.

## Implementation

If the recommended option is accepted: the edit-apply definition re-declares
the manual-override operand, and its executor consumes the value through the
executor context's operand access instead of the request. The request drops its manual values and returns to
credential-free journal storage under a new schema version. The edit
application service submits the values through operand custody, as the
observation decision specifies. The secure-reference conformance pin is
replaced by one asserting the operand declaration and the credential-free
request. The composition proofs return to the production declaring definition.
If the alternative is accepted instead, the retirement follows the no-legacy
rule: the protocol modules, custody store, submission path, composition guard
and their tests are removed together, and both decisions are amended.

## Rationale

The accepted design keeps a manual financial amount out of every durable store,
which is the strongest property available for it. Its protocol, custody
store and executor access are implemented; only the edit's own wiring was never
finished. Completing it closes
the contradiction with both decisions and gives the protocol back its designed
consumer. Ratifying the change would instead lower the protection for these
values without a stated reason.

## Consequences

- Manual edit values stop being persisted anywhere, including encrypted
  storage.
- The edit-apply request schema changes version again, and the intermediate
  stored-request shape needs explicit handling.
- The operand protocol regains a production consumer, and its composition
  proofs stop needing a test-only definition.
- If the alternative is chosen instead, the protocol's modules and tests are
  deleted, and both accepted decisions are amended to match.
