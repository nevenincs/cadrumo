---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---


# `cli-workflow-redesign` adr: `App ledger remove transaction` | (**status:** `accepted`)

## Problem Statement

`aeat app ledger import` is idempotent against re-importing the same source
file, but it cannot undo a transaction row created in error: a wrong-bank
import, a typo in a manual entry, a contaminated test import in the active
bucket. The ledger ADR provides `check` to report orphan and duplicate
blockers, but no verb to act on them. Without a removal path, the only
recovery is a full bucket restore — disproportionate to a single bad row.

## Considerations

- Ledger transactions are bucket-scoped persisted records. Removal is a
  durable mutation, not a soft state change.
- Removing a transaction must cascade: attached `purchase_invoice_evidence`,
  business-operation links to `payable_invoice` / `collectible_invoice`,
  classification state, allocation splits, and any review-queue items
  referencing the row must be either cleaned up or explicitly orphaned with
  bucket-event records.
- A transaction that is already cited by a `verified_complete` or `filed`
  modelo revision is part of the audit trail and must not be removed; the
  audit chain depends on it.
- Removal is distinct from `discard` (modelo work-unit state transition);
  `remove` here is a physical deletion within ledger scope.

## Constraints

- `aeat app ledger remove TRANSACTION_ID --by ACTOR [--reason TEXT]`
  removes a single transaction by stable id from the active bucket.
- The command rejects removal if the transaction is referenced by any
  `verified_complete` or `filed` modelo revision in the active bucket; the
  rejection error names the offending revision id and modelo selector.
- The command cascades to dependent records:
  - attached `purchase_invoice_evidence` rows: detach (preserve the
    evidence record itself; emit `purchase_invoice_evidence.detached`)
  - links to `payable_invoice` / `collectible_invoice`: break (emit
    `attachment.linked = false` correction)
  - review-queue items: mark resolved with reason "ledger transaction
    removed"
- The command emits a `ledger.transaction.removed` bucket event with the
  transaction id, actor, optional reason, and the list of affected
  dependent record ids.
- `aeat app ledger remove --dry-run` reports what would be removed and what
  cascades would apply, without performing any mutation.
- The command is bucket-scoped through the active profile.
- The command must never submit, transmit, or live-file data with AEAT.

## Implementation

Command shape:

```text
aeat app ledger remove TRANSACTION_ID
                       --by ACTOR
                       [--reason TEXT]
                       [--dry-run]
                       [--format json|text]
```

The `--by ACTOR` flag follows the actor-attribution ADR (defaults to
active-profile display name).

Pipeline:

- Resolve the transaction by stable id within the active bucket.
- Compute the dependency closure: evidence attachments, business-operation
  links, review-queue references.
- Check for blocking citations: any reference from a `verified_complete`
  or `filed` modelo revision rejects with `CliValidationBoundaryError`
  naming the offending revision and modelo selector.
- If `--dry-run`: emit the closure report and return without mutation.
- Otherwise: apply the cascade in a single logical transaction; emit the
  `ledger.transaction.removed` bucket event with the closure record.

Output:

- Text: "Transaction TX_ID removed (3 dependent records cascaded). Reason:
  ..." with the active-profile header.
- JSON: envelope with `transaction_id`, `state: "removed"`,
  `cascaded: {evidence_detached: [...], links_broken: [...],
  review_items_resolved: [...]}`, `actor`, `reason`, `event_id`,
  `bucket_id`.

## Rationale

Idempotent import protects against duplicate ingestion but is silent on
intentional removal. Operators routinely encounter bad imports and need a
proportionate recovery verb. Treating removal as a physical mutation
(not a soft state change) reflects the operator's mental model and keeps
the ledger's record set clean for modelo calculation. The audit-trail
guard prevents removal of transactions cited by durable modelo revisions,
preserving the integrity of verified/filed lifecycle artifacts.

## Consequences

- `aeat app ledger list` excludes removed transactions; there is no
  `--include-removed` flag because removed transactions are physically
  deleted (their record exists only as a bucket-event reference).
- The bucket event history surface (`aeat config bucket history`) renders
  `ledger.transaction.removed` events alongside other ledger events;
  history is the only post-removal trace.
- Tests must cover: removal succeeds on unreferenced transactions; removal
  refuses on transactions cited by verified/filed revisions; cascade
  reaches evidence, links, and review items; dry-run emits the closure
  report without mutation; the bucket event records the cascade list;
  removal is bucket-scoped and respects the active-profile header
  contract.
