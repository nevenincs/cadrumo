---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S367]]'
---

# `secure-storage-production-hardening` `W12.P26.S367` Review

## S367-001 | PASS | Transaction models do not own storage

`_models.py` defines strict immutable transaction records, derived identifiers,
catalogue validation, and the bucket-qualified `BucketTransactionRef` value. It does
not instantiate secure-object repositories, inspect active profiles, load settings,
open files, write manifests, connect to SQL, or persist plaintext.

## S367-002 | PASS | Encrypted repository boundary is centralized

`TransactionCatalogueRepository` owns transaction catalogue persistence under
`TX_BUCKET_NAMESPACE`. It resolves bucket storage through runtime inspection, stores
payloads as `SecureObjectWrite` records, wraps catalogue payloads in `Envelope`, and
uses `SensitivityClass.FINANCIAL`.

## S367-003 | PASS | Drift and integrity errors stay typed

Schema drift is wrapped as `StoredTransactionDriftError` with the stored-data
validation translation key and preserved `ValidationError`. Classification and envelope
version drift surface as storage integrity exceptions with structured context and
localized translation keys.

## S367-004 | FIXED | Roundtrip anti-drift tests imported the tests package

Five repository roundtrip tests imported `_repository` from the tests package. The
imports now target the production parent package, so the anti-drift tests exercise the
real repository constants and object-key helper.

## S367-005 | PASS | Runtime isolation gate proves bucket enrollment

`test_transaction_repository_default_isolates_bucket_writes` writes separate catalogues
under two active runtime buckets and proves bucket A cannot see bucket B's transaction
catalogue. This guards against default-route regressions.

## S367-006 | PASS | Locale scanner enrollment remains clean

`python -m aeat.locales audit` passes for all locale files. The CLI intracom
operation-type refusal keys are recognized by the canonical locale audit, so the
operator-facing error path remains enrolled in `tr()`.

## S367-007 | PASS | Validation

- `uv run --no-sync ruff check ...` passed for the transaction, repository, CLI, and
  runtime-isolation surfaces in scope.
- `uv run --no-sync pytest -q ...` passed 57 transaction tests.
- `uv run --no-sync pytest -q ... -k "transaction_repository_default_isolates_bucket_writes"`
  passed the runtime bucket-isolation test.
- `uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-265`; the scanner signal is a model-reference signal, not a
storage implementation risk.
