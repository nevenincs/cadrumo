---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
step_id: 'S367'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S367 - Close AFR-265 for transaction models

Scope: close `AFR-265` for `src/aeat/domain/transactions/_models.py` with signal
`manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`.

## Description

- Audited `_models.py` for direct manifest discovery, active-profile resolution,
  settings/environment access, filesystem IO, SQL access, secure-object construction,
  and plaintext persistence.
- Confirmed `_models.py` is a strict immutable pydantic model module. It defines
  transaction value records, catalogue invariants, derived identifiers, and
  `BucketTransactionRef`; it does not own persistence.
- Confirmed the encrypted persistence boundary is `TransactionCatalogueRepository`,
  which resolves runtime storage through `inspect_bucket_storage_runtime`, writes
  `TX_BUCKET_NAMESPACE`, and wraps payloads in `Envelope` records at
  `SensitivityClass.FINANCIAL`.
- Repaired the transaction repository roundtrip tests so anti-drift fixtures import
  `_TX_CATALOGUE_VERSION`, `TX_BUCKET_NAMESPACE`, and `transaction_catalogue_object_key`
  from the production repository package rather than the tests package.
- Verified the locale scanner now recognizes the intracom operation-type translation
  keys through the canonical `aeat.locales` audit.
- Closed `W12.P26.S367` through `vaultspec-core vault plan step check` and updated
  the `AFR-265` register status to `closed`.

## Outcome

`AFR-265` is closed. The `manifest-bucket` scanner signal is provenance from the
bucket-qualified reference model, not a concrete manifest-discovery or storage owner.
Transaction catalogue IO remains centralized in the encrypted secure-object repository.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py src/aeat/domain/transactions/_models.py src/aeat/domain/transactions/_repository.py src/aeat/domain/transactions/tests/test_repository_roundtrip.py src/aeat/domain/transactions/tests/test_models.py src/aeat/domain/transactions/tests/test_catalogue.py src/aeat/domain/transactions/tests/test_gross_invariant.py src/aeat/domain/transactions/tests/test_repository.py src/aeat/adapters/persistence/storage/tests/test_runtime_migrated_repositories.py`
- `uv run --no-sync pytest -q src/aeat/domain/transactions/tests/test_models.py src/aeat/domain/transactions/tests/test_catalogue.py src/aeat/domain/transactions/tests/test_gross_invariant.py src/aeat/domain/transactions/tests/test_repository.py src/aeat/domain/transactions/tests/test_repository_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/tests/test_runtime_migrated_repositories.py -k "transaction_repository_default_isolates_bucket_writes"`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

Subagent spawning was attempted for sidecar S367 discovery, but the agent thread limit
was already reached. The closure relies on direct source inspection and the focused
real-behavior gates above.
