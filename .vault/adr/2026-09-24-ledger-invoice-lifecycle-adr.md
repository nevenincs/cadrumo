---
tags:
  - '#adr'
  - '#ledger-invoice-lifecycle'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:b707da760c6f2ef4a270ea6a6da966e26668e2aa0041c58d23ba6e469f4a61fe'
related:
  - "[[2026-09-24-ledger-invoice-lifecycle-research]]"
---

# `ledger-invoice-lifecycle` adr: `Linked-ID edit refusal and atomic invoice audit write` | (**status:** `proposed`)

Proposed 2026-09-24. A development handoff dated 2026-09-22 states that the user accepted both choices below that day. That statement is recorded here but not confirmed, so this record stays proposed until the user confirms it.

## Problem Statement

Two ledger write paths lacked a defined contract (see `2026-09-24-ledger-invoice-lifecycle-research`). Editing a transaction that an invoice links to changes its content-derived ID, and no revision-guarded write swaps the invoice's `linked_transaction_ids` with it. Invoice create and update saved the catalogue and then emitted the audit event separately, so an event failure could leave a durable invoice with no audit history and a retry that fails on the duplicate-ID guard.

## Considerations

- Link creation already co-commits the reciprocal catalogues and the event in one secure-object batch, which is a precedent but not a correction policy.
- A local record correction, a rectifying invoice and an amended tax return are different acts.
- An event count or delivery acknowledgement does not prove recoverable prior invoice content.

## Considered options

Linked transaction identity edit:

- Keep refusing the edit, with the same typed refusal in CLI and TUI. Chosen.
- Define a linked correction contract: one atomic, revision-guarded write of the replacement transaction, the invoice's old-to-new ID swap, edit lineage, evidence references and durable audit intent, refusing stale baselines, collisions and wrong bucket or entity before mutation. Kept as a future design candidate; not authorized.

Invoice create and update audit:

- Commit the invoice catalogue and its audit event together under guarded revisions. Chosen.
- Keep save-then-emit and return a typed committed-with-audit-pending result, with an idempotent repair operation. Rejected: it adds a second visible state to both frontends to recover from a failure the atomic write avoids.

## Constraints

- The atomic write uses the existing secure-object co-commit boundary; no second persistence path.
- Notification delivery policy is outside this decision.
- A payment record or a tax-return amendment is outside the linked-edit choice.

## Implementation

A linked transaction's identity-changing edit is refused before persistence, in both frontends, with one typed outcome; unlinked edits keep their existing validated path. Invoice create and update write the catalogue and the audit event in one guarded batch: a failed batch commits neither, and a successful one returns the committed identity and event reference. As of 2026-09-24 the atomic write is in place (`src/cadrumo/application/invoices/catalogue_lifecycle.py:291`, `src/cadrumo/application/invoices/catalogue_creation.py:553`).

## Rationale

Refusal keeps both frontends consistent and loses no evidence, while the correction contract needs revision guarding the combined helper does not yet provide. The atomic audit write reuses a proven co-commit boundary and removes the invoice-without-history state rather than exposing it.

## Consequences

Operators cannot correct a linked transaction's identity until a correction contract is decided. Every invoice mutation has a durable audit event or did not happen. The import-identity policy for a changed invoice remains open and is not settled here.
