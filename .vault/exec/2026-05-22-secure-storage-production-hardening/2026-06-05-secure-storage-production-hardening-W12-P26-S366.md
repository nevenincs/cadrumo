---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S366'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S366 - Close AFR-264 for transaction errors

Scope: close `AFR-264` for `src/aeat/domain/transactions/_errors.py` with signal
`manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`.

## Description

- Audited the transaction error hierarchy for central AEAT error-base inheritance.
- Regrounded stored transaction drift against the stored profile drift precedent.
- Added the shared stored-data-validation translated message key, recovery context, and
  repair suggestion to `StoredTransactionDriftError`.
- Added a default financial-ledger storage translated message key to
  `LedgerStorageError` while preserving caller-provided messages and context.
- Extended existing transaction repository tests to assert translated-message metadata
  and recovery context.
- Closed `W12.P26.S366` through `vaultspec-core vault plan step check` and updated the
  `AFR-264` register status to `closed`.

## Outcome

`AFR-264` is closed. Transaction storage and drift failures now expose structured AEAT
error metadata while retaining typed exception inheritance and existing diagnostic
details.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/transactions/_errors.py src/aeat/domain/transactions/_repository.py src/aeat/domain/transactions/test_repository.py src/aeat/domain/transactions/test_repository_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/domain/transactions/test_repository.py src/aeat/domain/transactions/test_repository_roundtrip.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "transactions _errors StoredTransactionDriftError LedgerStorageError AeatError registered error code structured context" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "StoredProfileDriftError stored data validation bucket_id original_exception translated_message context" --type code --port 8766 --max-results 8`

## Notes

No translation files were edited; the implementation uses existing locale keys and the
locale audit was run through `python -m aeat.locales`.
