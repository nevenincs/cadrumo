---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S343]]'
---

# `secure-storage-production-hardening` `W12.P26.S343` Review

## S343-001 | PASS | Invoice catalogue default construction resolves runtime storage

`InvoiceCatalogueRepository` resolves an explicit bucket id when provided, otherwise
uses the active bucket resolver. Without an injected secure-object repository it calls
the bucket storage runtime inspector and obtains the runtime-created secure-object
repository for the selected bucket. No direct SQL path, plaintext JSON path, or ad hoc
default repository construction remains in the default production path.

## S343-002 | PASS | Persistence uses FINANCIAL secure-object envelopes

The repository saves `InvoiceCatalogue` through `SecureObjectRepository.save()` under
the `aeat.domain.invoices` namespace and `catalogue` object key with FINANCIAL
classification and schema version 1. Loads require FINANCIAL classification, enforce
the supported envelope version, and return an empty typed catalogue on absent secure
object with a debug breadcrumb.

## S343-003 | PASS | Tests exercise real runtime and anti-tautology behavior

The focused invoice repository tests use isolated runtime profiles, save and reload
real encrypted catalogue records, verify application invoice consumers route through
the selected bucket, and mutate stored payloads to prove identity drift is surfaced at
load time. The tests import production repositories directly and do not use fakes,
stubs, monkeypatches, skips, or mirrored business logic.

## S343-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/domain/invoices/_repository.py src/aeat/domain/invoices/test_repository.py src/aeat/domain/invoices/test_secure_storage_roundtrip.py src/aeat/application/invoices/test_linking.py src/aeat/application/invoices/test_queries.py src/aeat/application/invoices/test_reconciliation.py src/aeat/application/invoices/test_source_resolver.py` passed.
- `uv run --no-sync pytest -q src/aeat/domain/invoices/test_repository.py src/aeat/domain/invoices/test_secure_storage_roundtrip.py src/aeat/application/invoices/test_linking.py src/aeat/application/invoices/test_queries.py src/aeat/application/invoices/test_reconciliation.py src/aeat/application/invoices/test_source_resolver.py` passed with 22 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` passed with the known PLAN022 warning.
- `uv run --no-sync vaultspec-rag search "InvoiceCatalogueRepository inspect_bucket_storage_runtime secure object runtime active bucket financial envelope" --type code --port 8766 --max-results 8` returned runtime factory and invoice repository evidence.
- `uv run --no-sync vaultspec-rag search "runtime default repository load save SecureObjectRepository bucket id active profile InvoiceCatalogueRepository test_secure_storage_roundtrip" --type code --port 8766 --max-results 8` returned runtime-default repository tests and the invoice roundtrip coverage.

Reviewer note: no critical, high, medium, or low runtime-storage findings remain for
the S343 slice.

Disposition: close `AFR-241` as `runtime-default`.
