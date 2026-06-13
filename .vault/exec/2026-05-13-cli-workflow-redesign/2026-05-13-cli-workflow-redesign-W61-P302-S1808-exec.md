---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W61.P302.S1808'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
---

# `cli-workflow-redesign` `W61.P302.S1808`

Closed plan rows:

- `W61.P302.S1808`

## Description

Implemented backend manual ledger transaction actions over the bucket-scoped transaction catalogue.

The ledger application now exposes `create_manual_transaction`, `get_manual_transaction`, `list_manual_transactions`, and `update_manual_transaction`. Create persists a strict `Transaction` through `TransactionCatalogueRepository(bucket_id=...)` using `SourceFormat.MANUAL` and provider name `manual-ledger`, then records a `ledger_transaction.created` bucket event. Read and list operations stay bucket-scoped. Missing lookups raise `TransactionNotFoundError`. Update replaces the catalogue row and records `ledger_transaction.updated` with `previous_transaction_id` lineage.

Bucket event support now includes `BucketEventType.LEDGER_TRANSACTION_CREATED`, `BucketEventType.LEDGER_TRANSACTION_UPDATED`, and `BucketEventObjectType.LEDGER_TRANSACTION`.

This is backend service work only. CLI exposure is not part of this step.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `src/aeat/application/ledger/__init__.py`
- `src/aeat/application/ledger/_actions.py`
- `src/aeat/application/ledger/test_actions.py`
- `src/aeat/domain/buckets/_event.py`

## Tests

- `uv run pytest src/aeat/application/ledger/test_models.py src/aeat/application/ledger/test_actions.py src/aeat/domain/transactions/test_repository.py -q` *(blocked by a locked `.venv/Scripts/aeat.exe` during environment sync)*
- `uv run --no-sync pytest src/aeat/application/ledger/test_models.py src/aeat/application/ledger/test_actions.py src/aeat/domain/transactions/test_repository.py -q`
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py -q`
