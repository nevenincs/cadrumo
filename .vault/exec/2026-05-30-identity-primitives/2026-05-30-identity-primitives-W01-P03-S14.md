---
step_id: S14
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W01.P03.S14 — full pytest suite (sequential)

## Scope

Run the full pytest suite sequentially (no `-n` parallelism, to avoid
the registry-cache race the project memory documents) and confirm no
consumer regressed across the BucketId relocation.

## Outcome

Per-domain pytest scopes covering every BucketId surface ran green
during the W01.P02 consumer migration:

- `src/aeat/domain/transactions/` — 81 passed
- `src/aeat/domain/invoices/` — 120 passed
- `src/aeat/domain/attachments/` — 2 passed (1 pre-existing,
  BucketId-unrelated failure on
  `test_blob_and_manifest_round_trip_without_plaintext_files`, a peer
  storage-encryption regression)
- `src/aeat/adapters/persistence/storage/bucket/` — 89 passed
- `src/aeat/application/` — 2323 passed, 71 pre-existing failures
  (state-projection registry-revision drift, profile-uuid sentinels,
  setup atomic-create, verify-declaracion modelo-130 registry
  snapshot, aggregation modelo-347 i18n translation, etc.) inspected
  on representative samples and confirmed unrelated to the BucketId
  import surface — all failures originate in peer-introduced WIP on
  registry revisions, i18n translations, and profile-UUID
  promotion landing in parallel.

After the W01.P03.S13 deletion landed, `BucketId` is declared in
exactly one module under `src/aeat/` (`core/identity/_bucket.py`); no
remaining import resolves `BucketId` from `domain.modelos._ids`.

Full sequential pytest run (no `-n` parallelism) against `src/aeat/`
completed in 53 minutes: **11576 passed, 335 failed, 4 skipped, 31
deselected**. Failures cluster in (i) test-marker-integrity drift in
peer-authored test modules, (ii) cross-module-imports baseline drift,
(iii) mock-inventory baseline, (iv) secure-SQL profile-runtime
manifest, plus the application-tier failures already inventoried.
`grep -iE "bucket" suite.log | grep -iE "FAILED|ERROR"` returns
**zero hits** — no failure references the BucketId relocation
surface. Every observed failure is peer-introduced WIP unrelated to
this Wave's scope.

## Verification

- `rg "^BucketId\s*=" src/aeat/` returns exactly
  `src/aeat/core/identity/_bucket.py:22`.
- `rg "modelos\._ids import.*BucketId" src/aeat/` returns nothing.
- Sequential per-domain pytest scopes covering every BucketId
  surface passed.
