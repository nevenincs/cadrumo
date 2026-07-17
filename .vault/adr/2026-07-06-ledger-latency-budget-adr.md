---
tags:
  - "#adr"
  - "#ledger-latency-budget"
date: '2026-07-06'
related:
  - "[[2026-07-06-ledger-perf-optimization-research]]"
superseded_by: '2026-07-06-ledger-perf-optimization-adr'
modified: '2026-07-17'
---
# `ledger-latency-budget` adr: `dirty-set save semantics` | (**status:** `superseded`)

## Problem Statement

The read-path latency work brought the M130 calculate diagnostic under the 3.0s target,
but W05 measured a separate write-path residual: a one-row same-id ledger mutation over
the 30k-row encrypted fixture still takes multi-second time because
`TransactionCatalogueRepository.save()` reconciles a whole incoming catalogue. The S40
benchmark measured P95 `2.659s` for a single changed transaction. The named dominant
component is serializing and SHA-256 hashing every incoming transaction payload:
`1.399s` P95 for all-row serialize+hash versus `0.201s` P95 for the namespace payload
hash scan.

The current repository already stores one secure-object row per transaction and skips
rewriting unchanged rows. The remaining problem is not encrypted row rewrite
amplification; it is all-row CPU work done to discover the dirty row. Application
single-row mutation commands already know the changed transaction id, so this ADR
decides whether to introduce an explicit dirty-set save contract.

This ADR is proposed only. No dirty-set implementation is authorized until the operator
accepts or redirects this decision.

## Considerations

- `save_with_secure_object_writes` composes transaction writes with bucket-event and
  invoice writes in one secure-object `apply_batch`. Dirty-set writes must preserve that
  atomic co-write boundary.
- `_reconcile` currently loads membership ids, scans namespace payload hashes,
  serializes every transaction, hashes every payload, and returns changed writes plus
  deletions. It is conservative and remains the correct fallback for whole-catalogue
  imports, repair, and any caller without a proven dirty set.
- `_sync_date_index` derives the plaintext date index from the whole incoming catalogue.
  Dirty-set writes must update only affected date-index rows while keeping the index
  rebuildable and non-authoritative for tax correctness.
- Single-row mutation helpers such as manual update/classify already carry the old id,
  replacement transaction, and event set. Id-changing edits are already represented as
  replacing an old transaction id with a replacement id.
- Bulk classification already amortizes load-once/save-once across many rows. Dirty-set
  semantics should not make bulk paths less clear or less atomic.
- The previous latency ADR governs period-scoped reads and diagnostics. It is not
  superseded here; dirty-set writes are a separate mutation contract.

## Considered options

- **O1 - status quo full reconciliation.** Keeps the existing conservative path and
  preserves every contract, but S40 shows everyday one-row mutations still scale with the
  whole ledger. Rejected if mutation latency is a first-class optimization target.
- **O2 - process-local bytes/hash cache.** Cache serialized envelope bytes or payload
  hashes by transaction id and mutation stamp. This can reduce repeated serialization
  but extends plaintext-derived material lifetime in memory, is weak for process-per-
  command CLI use, and still leaves a full catalogue loop unless paired with dirty-set
  data. Rejected as the first decision; may be reconsidered after dirty-set measurement.
- **O3 - additive repository dirty-set API.** Add an explicit save path for known changed
  transactions and removed ids, preserving the existing full `save()` fallback. This
  makes single-row mutations scale with the dirty set while keeping the current
  reconciliation path for whole-catalogue callers. Recommended, pending approval.

## Constraints

- The existing full reconciliation path must remain available and must be the fallback
  when a caller cannot prove the changed ids or when index state is missing/stale enough
  that a delta cannot be applied safely.
- Deleted ids must be bounded by the encrypted membership index for the bucket; a
  dirty-set path must not delete rows outside the current bucket.
- Id-changing edits must be expressed as "remove old id, write replacement transaction."
  Same-id edits must not rewrite membership index rows unnecessarily.
- Date-index rows remain derived and rebuildable. Dirty-set date sync may update/delete
  only affected rows, but must not widen the plaintext schema or make the index
  authoritative.
- Unchanged transaction rows must remain untouched: revision id, payload hash, and
  ciphertext hash for unchanged rows must not change.
- Transaction writes, bucket-event writes, and invoice writes must still commit in one
  secure-object batch.
- This ADR depends on the already-landed per-transaction secure-object row store,
  membership index, atomic `apply_batch`, and date-index rebuildability. Those parent
  features are stable and currently covered by repository roundtrip and date-index tests.

## Implementation

High-level shape of O3, if accepted:

- Add an adapter-level dirty-set save method on `TransactionCatalogueRepository` for
  callers that already know the mutation delta. The method accepts changed/new
  `Transaction` rows, removed transaction ids, and sibling secure-object writes.
- The method loads the current encrypted membership ids, applies the delta to produce
  the new membership index, serializes only changed/new transactions, and either writes
  them directly or compares only their digests against stored payload metadata.
- The method creates secure-object deletions only for ids present in the current
  membership index and only within the transaction namespace/bucket key pattern.
- The method updates the membership-index row only when ids changed. It updates the
  plaintext date index only for changed/new/removed ids, using each changed
  transaction's filing date.
- The method calls `apply_batch` once with changed transaction writes, required
  deletions, membership-index write when needed, and sibling event/invoice writes.
- Existing `save()` and `save_with_secure_object_writes()` keep the full reconciliation
  behavior for whole-catalogue callers. Application single-row writers can be migrated
  to the dirty-set method only after acceptance tests pin the invariants above.

## Rationale

The measured residual is material and is not primarily the namespace hash scan. At 30k
rows, all-row serialize+hash is roughly seven times the namespace metadata scan and
accounts for about half of the real single-row save P95. A dirty-set write path attacks
the measured dominant component directly: changed-row serialization stays necessary,
unchanged-row serialization disappears.

The dirty-set contract is lower risk than a process-level bytes cache because it does
not extend plaintext envelope lifetime, does not depend on process reuse, and follows
facts already known by the mutation surface. It is also safer than replacing
`_reconcile`, because the full reconciliation path remains available for imports,
repair, and uncertain callers.

The decision is intentionally separate from the accepted period-read latency ADR. Read
optimization changed how period-scoped calculations avoid decrypting irrelevant rows;
dirty-set writes change mutation semantics and must preserve atomic co-writes and
revision metadata.

## Consequences

- **Good:** single-row ledger mutations can avoid serializing and hashing 29,999
  unchanged transactions at 30k-row scale.
- **Good:** the unchanged-row secure-object metadata contract becomes stronger: dirty
  writers should not even inspect or rewrite unchanged payload bytes.
- **Good:** the full reconciliation path remains available as a conservative fallback
  and as a repair/import boundary.
- **Cost:** repository mutation API complexity increases; callers must pass accurate
  changed/removed ids or fall back to full save.
- **Cost:** date-index sync gains a second, delta-based write path that must be tested
  against same-id date edits, id-changing edits, additions, and removals.
- **Risk:** a buggy dirty-set caller could omit a changed id and leave storage stale.
  Mitigation is to keep the API narrow, migrate only mutation helpers that already have
  exact old/new ids, and retain full-save fallback.
- **Approval gate:** this ADR is proposed. Implementation remains blocked until the
  operator accepts this decision or supplies a different write-path contract.
