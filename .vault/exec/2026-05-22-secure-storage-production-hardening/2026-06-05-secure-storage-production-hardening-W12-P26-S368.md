---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S368'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S368 - Close AFR-266 for raw transaction models

Scope: close `AFR-266` for `src/aeat/domain/transactions/_raw_transaction.py` with
signal `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`.

## Description

- Audited `_raw_transaction.py` as a model-only ingest boundary.
- Confirmed it has no secure-object, settings, environment, or file read/write route.
- Confirmed provenance paths are model data, not repository storage routes.
- Confirmed validation failures are typed under `TransactionValidationError`.
- Verified raw transaction behavior through inbound provider and adjacent transaction
  model tests.
- Closed `W12.P26.S368` through `vaultspec-core vault plan step check` and updated the
  `AFR-266` register status to `closed`.

## Outcome

`AFR-266` is closed. The raw transaction model file is a justified plaintext exception:
it defines immutable input-boundary records and does not participate in storage backend
selection or persistence.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/transactions/_raw_transaction.py src/aeat/domain/transactions/test_models.py src/aeat/domain/transactions/test_catalogue.py src/aeat/domain/transactions/test_gross_invariant.py`
- `uv run --no-sync pytest -q src/aeat/adapters/inbound/financial/providers/test_base.py`
- `uv run --no-sync pytest -q src/aeat/domain/transactions/test_models.py src/aeat/domain/transactions/test_gross_invariant.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "RawTransaction RawProvenance plaintext exception no storage no secure object transaction ingest model validation" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "transactions raw transaction provenance source_sha256 UTC validation MappingProxyType pydantic model tests" --type code --port 8766 --max-results 8`

## Notes

No production code change was required. The first attempted pytest selections for this
slice selected no tests or referenced a non-existent path; those invalid commands were
discarded and replaced with the valid validation commands listed above.
