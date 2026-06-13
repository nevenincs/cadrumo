---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S208]]'
---

# `secure-storage-production-hardening` `W12.P26.S208` Review

## S208-001 | PASS | Filing history repository is runtime-owned

`ModeloHistoryRepository` resolves default storage through
`resolve_application_filing_bucket_id()` and
`secure_objects_for_application_filing_bucket()`, then delegates persistence to
`SecureBoundRepository`. It does not construct a raw production
`SecureObjectRepository` when no repository is injected.

## S208-002 | PASS | Namespace, sensitivity, and schema are centralized

The repository uses `APPLICATION_FILING_HISTORY_NAMESPACE` for namespace,
`SensitivityClass.AUDIT`, and schema version. Existing tests prove persisted
filing history is encrypted in the active bucket SQL database and refuses a
foreign sensitivity class.

## S208-003 | PASS | Runtime refusal and profile isolation are covered

The migrated-runtime gate covers `ModeloHistoryRepository(bucket_id="bucket-a")`
for missing active bucket sessions and route-session mismatches. The same gate
also proves bucket A and bucket B history records remain isolated under active
runtime profiles.

## S208-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/filing/_history_repository.py src/aeat/application/filing/test_history_repository.py src/aeat/application/filing/test_history_repository_roundtrip.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py` passed.
- `uv run --no-sync pytest src/aeat/application/filing/test_history_repository.py src/aeat/application/filing/test_history_repository_roundtrip.py -q` passed with 19 tests.
- `uv run --no-sync pytest src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "filing_history or s85_runtime" -q` passed with 3 selected tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low findings remain for the S208
slice.

Disposition: close `AFR-106` as `runtime-default`.
