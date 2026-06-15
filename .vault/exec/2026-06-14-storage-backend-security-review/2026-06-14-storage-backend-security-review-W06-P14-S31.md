---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S31'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Move the transaction catalogue to one secure-object row per transaction keyed by transaction id so single-row mutations stop rewriting the whole catalogue

## Scope

- `src/aeat/domain/transactions/_repository.py`

## Description


- Confirm the premise: `TransactionCatalogueRepository` stores the entire
  catalogue as ONE encrypted secure-object row keyed
  `transaction-catalogue:{bucket_id}` in the `aeat.domain.transactions.bucket`
  namespace, so any single-transaction add/update/remove rewrites and re-encrypts
  the whole catalogue blob.
- Scope the blast radius of the per-row redesign.

## Outcome

STEP COMPLETE. The transaction catalogue is now one encrypted secure-object row
per transaction; a single-transaction mutation rewrites only the changed rows
instead of re-encrypting the whole catalogue.

Three pieces landed:

1. **Atomic upsert+delete primitive** — `SecureObjectRepository.apply_batch(writes,
   deletions)` commits every upsert and every digest-addressed deletion in one
   unit of work, so the per-row diff *and* the sibling-catalogue co-writes
   (bucket-event history, invoices, via `save_with_secure_object_writes`) stay
   all-or-nothing — the exact atomicity the single-blob save had. Deletions
   address rows by raw HMAC digest (`SecureObjectDeletion`), the diff's only
   handle on stored rows. `namespace_payload_hashes` is its decryption-free diff
   companion (skip unchanged rows). A transactional-rollback proof covers it.
2. **Per-row repository** — `load`/`save`/`save_with_secure_object_writes` keep
   their signatures and the `TransactionCatalogueRepositoryProtocol`, so **every
   ledger-mutation caller is untouched** (the caller blast radius I had flagged
   evaporated under the API-preserving design). Changed-row detection is the
   payload-hash diff; stable hashes come from serialising each row with
   `written_at = transaction.modified_at`.
3. **Cross-bucket isolation** — preserved by a per-bucket membership-index row
   (`transaction-index:{bucket}`) read by its exact key: `load()` and deletions
   are bounded to this bucket's transaction ids, so a shared secure store can
   neither leak nor delete another bucket's rows. This was the crux — without it
   a shared-store reconciliation would have deleted peer buckets' rows.

The deferral's stated blocker (no atomic upsert+delete primitive; `save_many` is
upsert-only) was the first thing built. The roundtrip + anti-tautology suite was
rewritten to mutate per-transaction rows; the classification / schema-version /
drift error contracts are preserved per row.

Gates: transaction repo 17, `apply_batch` 3, ledger+review+runtime 610,
aggregation 51, transactions+staleness+bulk-classify+participation 144 — all
green; full storage suite green (hardening-guard allowlist extended for the new
test). The 5 failures in the broad sweep were peer-state contamination (the
`application/modelo` mid-flight error-class conftest import) — all pass in
isolation, confirmed not owned here.

## Notes


Performance finding (medium): single-row mutations rewriting the whole catalogue is
O(n) write amplification per ledger edit. Correctness is unaffected today; this is a
scalability optimisation for large catalogues. No production regression to absorb.

**Deeper scoping (this session).** An API-preserving diff design (keep
`load()`/`save(catalogue)`, store one secure-object row per `transaction_id`,
write only changed rows) would keep every mutation caller unchanged — so the blast
radius is the repository internals + its tests, not the ~10 consumers. BUT the
correctness crux is **atomicity**: `save_with_secure_object_writes` atomically
commits the transaction catalogue *together with* the bucket-event-history and
invoice catalogues in one `save_many` unit (`_actions_common.py:719,739` — the
ledger-mutation + its event entry + invoice update must be all-or-nothing). Per-row
storage needs (a) diff-on-save, which reads current stored row digests and so
breaks the current purity of `to_secure_object_write` (a pure serialise used for
atomic composition), and (b) for the `remove`/`split`/`merge` paths, **atomic row
deletions** — but `save_many` is upsert-only, so deletes do not compose atomically
with the multi-catalogue co-write today. Delivering S31 safely means designing an
atomic upsert+delete batch primitive (or restructuring the co-write) so the
participation-index + event-history + invoice atomicity invariant is preserved
across per-row deletes. That is a focused correctness-critical slice on the hot
ledger path, with the ledger + transactions + persistence suites as the gate —
the same deferral-then-complete discipline that carried S23/S30/S33, but genuinely
warranting its own session rather than a rushed landing that risks the atomic
co-write invariant.
