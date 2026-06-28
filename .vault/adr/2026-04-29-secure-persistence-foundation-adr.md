---
tags:
  - '#adr'
  - '#secure-persistence-foundation'
date: '2026-04-29'
modified: '2026-04-29'
related:
  - "[[2026-04-29-secure-persistence-foundation-research]]"
  - "[[2026-04-30-secure-persistence-foundation-wave12-adr]]"
  - "[[2026-04-27-secure-persistence-foundation-adr]]"
---



# `secure-persistence-foundation` wave-3 adr | (**status:** `accepted`)

## Problem statement

Wave 3 lands the **financial-domain consumer migrations** under
the substrate. The wave's load-bearing deliverable is the
bank-import Kent moment that closes issue #216:
`aeat financial ingest --persist` parses a bank statement, normalises
the rows into `RawTransaction` records, persists them through the
governed boundary, and returns a per-file summary. Re-running the
same file is idempotent; concurrent imports serialise; the persisted
catalogue is encrypted at rest at the FINANCIAL classification.

The substrate is feature-complete after Wave 2. Wave 3 ships
**adapters** — read-through wrappers around the existing
`TransactionCatalogue` / invoice / usage-ratio / attachment APIs
that route writes through the substrate's
`Envelope[Payload]` + `EncryptedBlobStore` primitives.

## Considerations

Architectural drivers:

- The existing `aeat.domain.financial.transactions.TransactionCatalogue`
  is a strict frozen pydantic v2 model keyed by
  `derive_transaction_id`'s SHA-256 hash. The hash gives us
  idempotency for free: re-importing the same file emits the same
  transaction IDs, and a merge-on-write helper that skips
  duplicates is straightforward.
- The existing `load_transactions` / `save_transactions` helpers
  in `aeat.domain.financial.transactions._service` use atomic write via
  tempfile + `os.replace`. The substrate's `save_envelope` does
  the same. The migration is a thin wrapper, not a rewrite.
- The bank-import command (`aeat financial ingest`) currently
  prints `RawTransaction` JSON lines to stdout. Adding `--persist`
  adds a side effect; the existing pipe-to-file behaviour stays
  intact when `--persist` is OFF (default when stdout is not a
  TTY, per the issue body).
- Concurrency: parallel `aeat financial ingest --persist` calls
  on the same catalogue must serialise. The substrate's
  `exclusive_file_lock` is the natural primitive; the catalogue
  path drives the lock-file location.
- Public API discipline: callers continue to import from
  `aeat.domain.financial.transactions`; the new repository is internal
  (`_repository`).
- Read-through pattern: legacy `transactions.json` files remain
  readable; the adapter consults the substrate first and falls
  back to the legacy path with a one-shot deprecation log.
- No Alembic migration — the substrate is JSON-envelope-backed
  for file-shaped catalogues; SQL is used only for the
  catalogue-metadata storage layer (modelos / portals / etc.).
- The Kent success moment must be testable end-to-end: parser →
  repository → re-read → re-import → 0 new rows. Tests use real
  cryptography, real on-disk persistence, real `multiprocessing`
  for the concurrency invariant. No mocks.

## Constraints

- Python 3.13+, Windows-supported. No new runtime dependencies.
- Pydantic v2 strict frozen at every boundary.
- Trilingual error envelope contract for any new error class
  introduced by Wave 3 (the substrate's existing classes cover
  most cases; new cases are limited to the bank-import command's
  `LockAcquisitionError` exit-code mapping, which is already
  registered).
- Live AEAT submission permanently forbidden — Wave 3 does not
  touch live-submit territory.
- Coverage floor 60% on `src/aeat` preserved.
- Branch stays `feature/216-bank-import-persistence`; per-wave
  merges do not happen.

## Implementation

### Phase 0 — Wave-2 audit-gate finding cleanup

Action any HIGH / MEDIUM finding the Wave-2 reviewers raise that
has not yet been actioned by the time Wave 3 begins. Same pattern
as Wave-2 Phase 0/1.

### Phase 1 — TransactionCatalogue repository adapter

New module `aeat.domain.financial.transactions._repository` with:

- `TransactionCatalogueRepository(*, store_dir, master_key_provider=None)`
  — wraps the substrate's envelope helpers.
- `load() -> TransactionCatalogue` — reads
  `Envelope[TransactionCatalogue]` from
  `<store_dir>/transactions.envelope.json`; returns the empty
  catalogue when the file is absent.
- `save(catalogue: TransactionCatalogue) -> None` — writes via
  `save_envelope` at FINANCIAL class. Acquires the exclusive
  file lock for the duration.
- `merge_raw_transactions(raw_transactions: Iterable[RawTransaction], *, direction_resolver) -> ImportSummary`
  — the bank-import write path. Computes `derive_transaction_id`
  per row, skips IDs already in the catalogue (idempotency),
  builds `Transaction` records for new rows, persists the merged
  catalogue. Returns `ImportSummary(imported=N, skipped=M, errors=0)`.

The existing `aeat.domain.financial.transactions._service.load_transactions`
and `save_transactions` become read-through wrappers: they consult
the repository first; on `EnvelopeFileMissingError` (or simply
"no envelope yet") they fall back to the legacy
`<path>/transactions.json` shape with a one-shot deprecation log.
A migration helper
`migrate_transactions_to_governed_persistence(legacy_path,
store_dir)` reads the legacy catalogue and writes the envelope.

### Phase 2 — invoice catalogue adapter

`aeat.domain.financial.invoices._repository` mirrors Phase 1's shape for
the invoice catalogue. FINANCIAL class. Same read-through and
migration helper pattern.

### Phase 3 — usage-ratio adapter

`aeat.domain.financial.usage_ratios._repository` mirrors the same
pattern. FINANCIAL class. Smaller scope.

### Phase 4 — attachment store migration

The existing `aeat.domain.financial.attachments._store` is already
content-addressable (`blobs/{sha256}` + manifest JSON). Wave 4
migrates it to the substrate's `EncryptedBlobStore`. The blob
store's manifest layout is a superset of the existing one; the
migration helper reads the existing blobs and writes them through
the substrate's `EncryptedBlobStore.put`.

### Phase 5 — bank-import `--persist` wiring

The existing `aeat financial ingest` command grows two new flags:

- `--persist / --no-persist`. Default: ON when stdout is a TTY;
  OFF when stdout is piped. Honours the user's existing pipe-
  to-file workflow.
- `--catalogue PATH`. Optional override for the catalogue
  location; defaults to `aeat_financial_txs_dir`.

When `--persist` is active, parsed rows flow into the new
`TransactionCatalogueRepository.merge_raw_transactions`.
The command prints (and emits in `--json` mode via the existing
schema registry):

```
imported N rows; skipped M duplicates; 0 errors
```

Trilingual: the user-facing summary is emitted via the
Translatable pattern; ES default + EN explicit. Hungarian
support per the project mandate.

### Phase 6 — concurrency hardening

`merge_raw_transactions` acquires
`exclusive_file_lock(<catalogue_path>.lock)` for the duration of
the merge. A second concurrent import gets `LockAcquisitionError`
with exit code 7 (LOCKED) per the existing error code table.
Tests use real `multiprocessing.spawn`.

### Phase 7 — bank-import Kent-moment integration test

`tests/integration/test_bank_import_kent_moment.py` (new) runs
end-to-end against a synthetic bank-statement fixture:

1. `aeat financial ingest --persist --provider bbva --file
   <fixture>` succeeds; summary reports `imported N`.
2. Re-running the same command reports `imported 0; skipped N`.
3. Two concurrent invocations (real subprocesses) result in one
   success + one exit-7-LOCKED.
4. The persisted file on disk is a non-CORPUS envelope
   (FINANCIAL class) — content-grep confirms ciphertext at rest.

The test marker is `[pytest.mark.unit, pytest.mark.domain_financial_input]`.

### Phase 8 — TDP coverage matrix flip

`docs/coverage/pipeline.md` T1 row updates from
`🚧 (no persist)` to `✅ persisted via aeat financial ingest --persist`
with citation to the closing PR commit. This is the
operator-visible signal that the bank-import gap is closed.

### Phase 9 — Wave-3 audit gate

Identical contract to Waves 1 and 2. `vaultspec-code-review` over
every Wave-3 file plus a fresh OWASP security audit narrowed to
the financial-domain surface. Cycle until no CRITICAL or HIGH
finding remains; emergent findings either close in Wave 3 or roll
into Wave 4 research.

## Rationale

The phase ordering puts the smaller / simpler adapter migrations
first (Phases 1-3) so the bank-import wiring (Phase 5) has a
fully-tested foundation. The attachment-store migration (Phase 4)
is logically independent and could shift to a later wave if
operator-visible work pressure demands it; this wave's load-bearing
deliverable is the Kent-moment integration test (Phase 7), which
depends only on Phases 1, 5, and 6.

The read-through pattern is non-negotiable: legacy
`transactions.json` files remain readable until the operator runs
the migration helper. The deprecation log fires once per process
per resolved legacy path; operators see exactly one deprecation
notice per credential file regardless of how many times the
read-through path is hit.

The `derive_transaction_id` SHA-256 hash IS the idempotency key.
Re-importing the same file produces the same IDs; the merge helper
skips IDs already present. This sidesteps the entire "unique
constraint on (provider, account, date, amount)" approach that the
audit's HIGH-1 referenced; the existing hash gives us idempotency
without a SQL schema.

The classification choice is FINANCIAL across the board for the
financial-domain consumers. Attachments default to FINANCIAL too;
the substrate's classification primitive supports per-record
overrides if a future operator workflow uploads a public-corpus
attachment alongside an operator one.

## Consequences

Positive:

- Issue #216's bank-import Kent moment is implemented end-to-end.
- Every financial-domain consumer is **classified at rest** at
  FINANCIAL classification — every envelope's `classification`
  field is enforced at load time so a foreign-class envelope at
  the canonical path is refused. **Ciphertext-payload at rest
  remains a follow-up wave**: the substrate's
  `EncryptionMetadata` + `EncryptedBlob` primitives are ready,
  but `TransactionCatalogueRepository.save` writes the payload
  as plaintext-pydantic-JSON inside the envelope today. Wave 4
  wires `encrypt_record` into the repository's save path and
  adds a leak-canary regression test before declaring full
  encryption-at-rest. The classification gate already gives
  consumers integrity-against-cross-class-replay; the missing
  piece is confidentiality-against-on-disk-disclosure for the
  payload bytes.
- Idempotency falls out of the existing SHA-256 design; no
  schema migration is required.
- Concurrent imports are race-free via the substrate's
  cross-platform file lock.
- The TDP T1 row flips green; downstream waves (T6 aggregation,
  bulk-classify, VAT classification) are unblocked.

Negative:

- Operators with existing legacy `transactions.json` files must
  run the migration helper to encrypt their financial state.
  Wave 3 ships the helper and the deprecation log; a future ADR
  will set the legacy-removal milestone.
- The ImportSummary pydantic record introduces one new public
  shape; downstream consumers (Kent's eventual dashboard) need
  to consume it via the registered `--json` schema rather than
  parsing stdout.

Neutral:

- No new runtime dependencies.
- No Alembic migration.
- Wave 3 does not yet rewire the pre-Wave-2 consumer call sites
  in `aeat.entrypoints.cli.financial.txs` etc. — the Wave-2 read-through
  adapter pattern is the bridge. The rewires land opportunistically
  alongside the per-domain adapter wiring.

## Out of scope

- Filing / submission migration (Wave 4).
- Observability redaction discipline (Wave 5).
- Caches and corpora (Wave 6).
- Connector + export governance (Wave 7).
- Multi-currency / FX handling (#103 territory).
- PDF invoice ingest (#254 EPIC).
- Bulk-classification rules engine (#217).
- T6 period-close aggregation (#218; consumes Wave-3's persistence).
- VAT classification CLI wiring (#255).
- DecisionProvenance pydantic model (#352).
