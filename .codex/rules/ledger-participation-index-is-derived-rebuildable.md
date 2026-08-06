---
name: ledger-participation-index-is-derived-rebuildable
trigger: always_on
---

# Ledger participation index is derived and rebuildable

## Rule

The transaction-to-revision participation index is a derived encrypted cache co-written atomically with revision persistence and must be rebuildable from the revision catalogue; lifecycle correctness must rely on the live catalogue scan, never on index freshness.

## Why

The `2026-06-10-ledger-modelo-crossref-adr` introduced the participation index for operator cross-reference and audit navigation, not as a new source of truth. If deletion guards or filing correctness depended on the cache, a stale or missed index write could silently permit destructive ledger changes. Rebuildability keeps the index useful without making correctness depend on denormalised state.

## How

- Good: verification or filing persistence co-emits participation entries in the same secure-object write batch as the revision state change.
- Good: a rebuild action scans finalized revision catalogues and regenerates every per-transaction participation entry.
- Good: ledger removal blockers continue scanning the live revision catalogue.
- Bad: allowing a ledger transaction delete because the participation index has no entry for it.
- Bad: writing a plaintext participation index outside the active profile's encrypted secure-object repository.
