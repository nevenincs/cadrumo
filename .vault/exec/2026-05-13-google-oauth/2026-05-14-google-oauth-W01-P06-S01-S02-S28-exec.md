---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S01+S02+S28'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-05-13-google-oauth-taxonomy-adr]]"
---

# `google-oauth` `W01.P06.S01+S02+S28` — substrate enumeration + SourceKind drift acknowledgement

Three plan substeps reconciled against codebase reality:

- **S01 (already satisfied)**: `SecureObjectRepository.list_namespaces()` already exists at `src/aeat/adapters/persistence/storage/sql/secure_objects.py:184` returning the distinct namespace tuple sorted ASC. Outbound sync coordinator consumers should use this method; no new code lands for S01.
- **S02 (new code)**: `SecureObjectRepository.iter_all_records_raw(*, batch_size=256)` lands. Memory-bounded generator that yields every row in `(namespace ASC, object_key ASC)` order without attempting decryption — the outbound sync coordinator's ciphertext-layer mirror (per ADR-3) consumes this.
- **S28 (drift)**: `SourceKind` enum already exists at `src/aeat/application/operator_surface/_models.py:25` with the four canonical values. The plan said to land it at `src/aeat/domain/source_kind/__init__.py`. Per the user's earlier "remove duplications and consolidate everything, ensure everything is cohesively named" directive, NO duplicate is created. Subsequent P06 consumers (reverse-merge services, label derivers, prefix router, bucket-event emitter) import the existing `SourceKind` from `aeat.application.operator_surface`.

## Changes

- Created: `SecureObjectRawRow` pydantic record at `src/aeat/adapters/persistence/storage/sql/secure_objects.py:107` — frozen, strict, extra-forbid; carries `(row_id, namespace, object_key, classification, schema_version, written_at, payload)` with the payload as on-wire ciphertext bytes
- Created: `SecureObjectRepository.iter_all_records_raw(*, batch_size=256)` — bypasses the encrypted-column type decorators via a raw `text("SELECT ...")` query so rows sealed under a rotated master key still surface verbatim
- Created: 3 unit tests at `src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` covering: every row yields with on-wire ciphertext + metadata across multiple namespaces, empty-table case yields nothing without raising, rotated-master-key case still surfaces rows verbatim (no `DecryptionError`)

## Description

The raw iterator is intentionally classification-blind and version-blind. Where `iter_records_with_failures` runs the decryption + version-validation pipeline per row, `iter_all_records_raw` only reads the on-wire bytes. This matters because:

- The outbound sync coordinator (P03+) mirrors objects at the ciphertext layer per ADR-3 §1. Decrypting would defeat the security model (the local master key never leaves the host) AND would force mirroring to fail on rows sealed under any non-current master key.
- During a master-key rotation window, the substrate may temporarily hold rows under both the previous and current key. Mirroring should keep working uninterrupted.

The bypass uses a raw `text("SELECT ... FROM secure_objects ORDER BY namespace, object_key")` so SQLAlchemy's `EncryptedString` / `EncryptedBytes` type decorators don't fire. `yield_per(batch_size)` keeps memory bounded for very large substrates.

## Tests

- `pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q` — 8 passed (5 pre-existing + 3 new).
- `ruff check src/aeat/adapters/persistence/storage/sql/{secure_objects,test_secure_objects}.py` — clean.
- Coverage: 3-namespace ordered emission across 2 SensitivityClasses, ciphertext-verbatim assertion (payload bytes are NOT one of the plaintext values), empty-table empty-iterator, rotated-master-key non-raising case.

## P06 outstanding

- S03/S03a/S03b: per-source-kind repositories with `iter_*` (PurchaseInvoiceEvidence, PayableInvoice, CollectibleInvoice)
- S05-S08: reverse-merge services per source kind
- S09-S13: filing + deadlines + workflow result export hooks
- S14-S24: per-namespace `NamespaceLabelDeriver` registrations (depends on P03.S04-S06 deriver Protocol + registry)
- S25: `NamespaceAllowList`
- S26: sensitive-persistence policy test extension
- S29: extend `BucketEventType` enum with 6 new `LEDGER_*_CORRECTION_APPLIED` values
- S30: `src/aeat/entrypoints/cli/_app/` package skeleton
