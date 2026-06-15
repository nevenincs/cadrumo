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

STEP DEFERRED — large persistence-model redesign, focused follow-up.

Moving to one secure-object row per transaction (keyed by transaction id) is a
clean target and the no-legacy rule means a straight cutover (no migration: delete
the whole-catalogue shape, ship the per-row shape). But the blast radius is the hot
ledger path and every reader of the catalogue:

- the repository read/write API (whole-catalogue load/save -> per-row load,
  namespace enumeration for list-all, single-row upsert/delete for mutations);
- the derived participation index
  (`ledger-participation-index-is-derived-rebuildable`) and its co-write atomicity;
- reconciliation, aggregation, and CLI consumers that load the catalogue;
- the uniform-quintet mutation contract (`ledger-mutation-returns-uniform-quintet`);
- the catalogue roundtrip + anti-tautology persistence tests (the whole-catalogue
  fixtures rewrite to per-row).

This is a self-contained campaign-sized slice that must land atomically with full
roundtrip coverage, not an end-of-session edit on the hot path. Deferred to a
focused pass with the ledger + persistence suites as the gate — the same
deferral-then-complete discipline that carried S23.

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
