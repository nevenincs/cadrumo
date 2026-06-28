---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S365'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S365 - Close AFR-263 for submission repository

Scope: close `AFR-263` for `src/aeat/domain/submission/_repository.py` with signal
`secure-bound`, target `runtime-default`, and owner `W12.P21.S84`.

## Description

- Regrounded `SubmissionRepository` against the runtime-owned secure object repository.
- Replaced fail-fast id iteration in `iter_submissions` with failure-aware secure
  record iteration.
- Logged unreadable secure-object outcomes with row identifiers and failure reasons.
- Logged invalid decrypted submission payloads with traceback context before skipping
  them.
- Preserved deterministic iteration order by sorting healthy records by submission id.
- Added real-storage coverage for a future secure-object schema row mixed with a healthy
  submission row.
- Updated the adapter classification gate test to assert the structured AEAT
  `ClassificationError` payload.
- Closed `W12.P26.S365` through `vaultspec-core vault plan step check` and updated the
  `AFR-263` register status to `closed`.

## Outcome

`AFR-263` is closed. Submission persistence remains secure-bound and runtime-default,
and submission iteration now honors its documented skip-unreadable-row behavior without
silent exception swallowing.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/submission/_repository.py src/aeat/domain/submission/test_repository.py src/aeat/domain/submission/test_secure_storage_roundtrip.py src/aeat/adapters/persistence/storage/test_submission_repository.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py`
- `uv run --no-sync pytest -q src/aeat/domain/submission/test_repository.py src/aeat/domain/submission/test_secure_storage_roundtrip.py src/aeat/adapters/persistence/storage/test_submission_repository.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "submission or SubmissionRepository"`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`
- `uv run --no-sync vaultspec-rag search "SubmissionRepository SecureBoundRepository iter_submissions iter_records_with_failures AUDIT runtime-default secure-bound" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "SubmissionRepository SecureBoundRepository audit enumeration unreadable row iter_records_with_failures secure object" --type code --port 8766 --max-results 8`

## Notes

This step deliberately avoided S298 and concurrently active modelos and transactions
files. The only adjacent test update was the submission adapter classification gate,
which now follows the structured AEAT exception contract.
