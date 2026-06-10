---
tags:
  - '#adr'
  - '#ledger-modelo-crossref'
date: '2026-06-10'
related:
  - "[[2026-06-10-ledger-modelo-crossref-research]]"
---

# `ledger-modelo-crossref` adr: `Persisted transaction participation index for audit cross-reference` | (**status:** `accepted`)

## Problem Statement

The ledger is a legally-binding record that must survive a tax audit, yet its
cross-reference to the modelo calculation and filing layer runs in only one
direction. A `CalculationRevision` persists `source_transaction_ids` (forward:
revision then transactions), and `LedgerFilingSnapshot` plus
`LedgerFilingEvidence` bundle the per-contributor tax facts pegged to the
revision's snapshot fingerprint. The inverse question an auditor actually asks
of a single transaction, namely which finalized modelo revisions, filings, and
justificantes consumed it, has no surfaced answer. The inverse is computed only
in memory by `_blocking_modelo_references`, a full scan of the calculation
revision catalogue used exclusively as a lifecycle write-guard, never exposed to
an operator. The filing receipt `ModeloRecord` stores only
`calculation_revision_id`, so transaction then filing is a two-hop traversal an
external tool cannot perform from a transaction id alone. The result is a
legally-binding store that cannot, on its own surface, explain where any one of
its rows was declared.

## Considerations

The forward link is complete and persisted and must not be disturbed. The
write-guard already answers the inverse for the three finalized states
(`VERIFICADO_COMPLETO`, `PRESENTADO`, `PRESENTADO_SUPERSEDIDO`); the gap is
purely a read-side and persistence question, not a computation one. The
`Transaction` aggregate is frozen and content-addressed: its id is a digest of
its fields, so a mutable "which revisions used me" set cannot live on the
transaction without breaking the content address (the same reason
`ledger_filing_snapshot` is excluded from `derive_calculation_revision_id`). An
atomic multi-object write primitive already exists
(`save_with_secure_object_writes`) and is the template for co-emitting a second
object in the same encrypted transaction as the revision save. The
secure-storage mandate binds: any new persisted artefact is critically
sensitive financial data and must be encrypted and bucket-scoped.

## Constraints

The index must not mutate the content-addressed `Transaction`. The index update
must co-emit atomically with revision persistence rather than re-implement the
revision write path (per the composition-service single-writer discipline). The
lifecycle write-guard must keep its authoritative live catalogue scan; the index
serves the read path only and is therefore allowed to lag a concurrent revision
save. The index must be a derived cache that is fully rebuildable from the
revision catalogue, so a stale or corrupt index is never a second source of
truth. A new registered encrypted bucket-scoped secure-object namespace is a
hard precondition.

## Implementation

Introduce a `TransactionRevisionParticipationIndex` secure-object, bucket-scoped,
recording for each transaction id the set of participations: the
`calculation_revision_id`, `work_unit_id`, `modelo`, `filing_year`, `period`,
and `revision_state`, plus, where the revision is filed, the `filing_record_id`
and the justificante reference. The index is maintained by co-emitting an index
update inside the same `save_with_secure_object_writes` atomic write that
`persist_calculation_revision` and `persist_filed_revision` already perform, so
the index and the revision land or fail together. Scope is finalized revisions,
matching the legal-audit guarantee and the existing guard states; borrador
inclusion (a pre-mutation "referenced in a pending draft" warning) is explicitly
deferred and noted, because it would add an index write to every calculate and
discard for a UX gain the legal mandate does not require.

The inverse is surfaced through a dedicated read verb, `ledger participation
<transaction-id>`, returning a typed `LedgerTransactionParticipationPayload`
carried on the uniform ledger response envelope; the existing `ledger track`
lineage output gains a parallel `participated_in` section so the audit trail is
visible from the lineage surface too. A `--include-borradores` flag is reserved
for the deferred borrador scope. The filing receipt `ModeloRecord` gains a
denormalized `source_transaction_ids`, excluded from `derive_filing_record_id`
(mirroring the snapshot exclusion on the revision hash), so an external audit
tool holding only a filing record resolves its transaction set in one hop. A
post-roundtrip validator cross-checks that `ledger_filing_snapshot.rows` and
`ledger_filing_evidence.rows` cover the same contributor set on read-back, so an
envelope that drops a row after persistence is caught rather than silently
trusted.

### Locked decisions inherited from the epic

Amounts in any evidence projection this verb surfaces are non-negative
magnitudes with an authoritative `direction` (per the absolute-amount
convention). The participation payload is a typed schema on the shared response
envelope, never a bare dict. No legacy or migration path is carried: the index
is a new artefact built forward from the current revision catalogue.

## Rationale

The participation index completes the posture the filing-snapshot decision
already declared, where the write-time block is the defense and the snapshot is
the audit and staleness layer; the index is the read-side audit layer that makes
the staleness and participation facts queryable. Choosing a derived, rebuildable
secure-object over a field on the transaction preserves the content-addressing
invariant the whole ledger relies on, and choosing co-emission over a parallel
writer preserves the single-writer atomicity that keeps the encrypted stores
from drifting. Keeping the live scan in the write-guard means correctness never
depends on index freshness; the index buys operator and auditor query speed, not
safety.

## Consequences

The system gains an auditable transaction-to-declaration trail and an O(1)
operator query for "where was this transaction declared", closing the legal-audit
gap. The denormalized filing footprint makes external audit tooling one-hop. The
costs are honest: an extra encrypted object write on every revision persist and
file; an index that is eventually-consistent with respect to a concurrent save
(acceptable because it is rebuildable and the guard is authoritative); a new
secure namespace to register and roundtrip-test; and an obligation to maintain
the index rebuild path so a corrupt or stale index can be regenerated from the
revision catalogue. The principal pitfall is treating the index as authoritative;
the design deliberately keeps the revision catalogue as the source of truth and
the write-guard on the live scan to prevent that.

### Secure-storage gate

The `TransactionRevisionParticipationIndex` rides a newly registered encrypted,
bucket-scoped secure-object namespace, written atomically with the revision
inside the active profile bucket; no plaintext index is ever written to disk.
The denormalized `source_transaction_ids` on `ModeloRecord` stay inside the
existing encrypted filing-record namespace. Roundtrip and anti-tautology tests
exercise the real encrypted store and reconstruct participation from real
revisions, never mocks.

## Codification candidates

- **Rule slug:** `ledger-participation-index-is-derived-rebuildable`.
  **Rule:** The transaction-to-revision participation index is a derived cache
  co-written atomically with revision persistence and MUST be rebuildable from
  the revision catalogue; the lifecycle write-guard relies on the live catalogue
  scan, never on the index, so correctness never depends on index freshness.
