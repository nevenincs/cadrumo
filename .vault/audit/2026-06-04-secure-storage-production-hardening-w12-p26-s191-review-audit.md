---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:76f2e73edb365d46d0f4e78bf3729e4fa199f37c32289addd018a18bc8b815b5'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S191` Review

## S191-001 | PASS | Repository persistence failures degrade through source mesh

`_modelo_bindings.py` now includes `TransactionPersistenceError` and `InvoicePersistenceError` in `_STORAGE_DEGRADATION_ERRORS`. This keeps repository-level persisted-catalogue failures on the same `storage_degraded` diagnostic route as secure-object classification, decryption, and envelope-version failures.

## S191-002 | PASS | Drift coverage uses real encrypted storage

The new source-mesh test writes malformed transaction-catalogue payload bytes through the real `SecureObjectRepository`, then resolves IVA ledger bindings through `TransactionCatalogueRepository`. The repository raises persisted-catalogue drift and the resolver returns an empty resolution with a `storage_degraded` diagnostic.

## S191-003 | PASS | Storage ownership remains centralized

The modelo binding module still does not read or write storage directly. It coordinates aggregation repositories and source-mesh diagnostics; secure-object persistence stays in the domain repositories and storage substrate.

Validation:

- the historical check passed with 5 tests.
- the historical check passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -c "from aeat.application.aggregation._modelo_bindings import LedgerIvaAggregationSourceResolver; print(LedgerIvaAggregationSourceResolver.resolver_id)"` printed `ledger_iva_aggregation`.

Reviewer note: supervisor review found no critical or high issues in the S191 slice. The remaining source issue messages are diagnostic payloads from aggregation issue records; this row only hardens degraded storage routing.

Disposition: close `AFR-089`.
