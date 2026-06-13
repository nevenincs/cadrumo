---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S367'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S367 - Close AFR-265 for transaction models

Scope: close `AFR-265` for `src/aeat/domain/transactions/_models.py` with signal
`manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`.

## Description

- Audited `src/aeat/domain/transactions/_models.py` for secure storage, runtime
  settings, direct environment access, filesystem IO, and remote-provider IO.
- Confirmed the file is a strict immutable Pydantic model and payload-shape surface.
- Confirmed the manifest-bucket signal is carried by `BucketTransactionRef.bucket_id`
  and the bucket-qualified transaction catalogue references.
- Confirmed encrypted runtime persistence is owned by
  `src/aeat/domain/transactions/_repository.py`, including
  `TX_BUCKET_NAMESPACE`, `transaction_catalogue_object_key`, and runtime-created
  secure-object repository resolution through centralized settings.
- Fixed relocated-test imports in transaction catalogue roundtrip, manual ledger
  command roundtrip, and workflow catalogue-resolution tests so verification exercises
  the current package layout.
- Closed `W12.P26.S367` through `vaultspec-core vault plan step check` and updated
  the `AFR-265` register status to `closed`.

## Outcome

`AFR-265` is closed as `manifest-discovery`. No production code change was required:
`_models.py` remains a schema and catalogue-reference boundary, while `_repository.py`
continues to own encrypted storage, runtime orchestration, active bucket binding, and
settings-backed secure-object repository creation. Focused verification also stabilized
three moved-test import sites affected by the concurrent test topology refactor.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/transactions/_models.py src/aeat/domain/transactions/_repository.py src/aeat/domain/transactions/tests/test_models.py src/aeat/domain/transactions/tests/test_catalogue.py src/aeat/domain/transactions/tests/test_repository_roundtrip.py src/aeat/application/ledger/tests/test_manual_ledger_transaction_command_roundtrip.py src/aeat/application/workflow/tests/test_transaction_catalogue_resolution.py`
- `uv run --no-sync pytest -q src/aeat/domain/transactions/tests/test_models.py src/aeat/domain/transactions/tests/test_catalogue.py src/aeat/domain/transactions/tests/test_repository_roundtrip.py src/aeat/application/ledger/tests/test_manual_ledger_transaction_command_roundtrip.py src/aeat/application/workflow/tests/test_transaction_catalogue_resolution.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "transaction catalogue bucket_id secure object repository manifest discovery payload model duplication" --type code --port 8766 --max-results 8`

## Notes

The locale audit was run through `python -m aeat.locales`. It passed without catalog
changes after the current business-invoice CLI split became visible to the locale
scanner. A separate RAG query for the same slice timed out on port 8766; the successful
query returned transaction repository, secure-object, and bucket-id evidence.
