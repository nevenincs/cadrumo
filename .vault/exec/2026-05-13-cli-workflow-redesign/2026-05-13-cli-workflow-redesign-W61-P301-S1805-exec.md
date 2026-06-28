---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W61.P301.S1805'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-w61-p301-s1801-ledger-storage-ownership-audit]]"
---

# `cli-workflow-redesign` `W61.P301.S1805`

Closed plan rows:

- `W61.P301.S1805`

## Description

Verified and hardened the ledger import and review projection paths against the bucket-scoped transaction catalogue contract.

`aeat app ledger import` now returns the backend `bucket_id`, `imported_transaction_refs`, and `skipped_transaction_refs` from `ImportSummary` in JSON output. The command remains a thin renderer of backend values. The encrypted ledger import regression creates a real active profile bucket, imports through the CLI, and reads the persisted transaction from the active bucket's `TransactionCatalogueRepository`.

Review projections already call `transactions_pending(settings, bucket_id=...)` and `transactions_low_confidence(settings, bucket_id=...)`, which load `TransactionCatalogueRepository(bucket_id=bucket_id)`. Added regression coverage proving a pending transaction stored under `other-profile` is invisible when the review adapter is asked for `active-profile`, while remaining visible for `other-profile`.

Removed a stale test expectation for the retired root-level `aeat review show` spelling. The review adapter emits `aeat app review show`, matching the current root contract.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `src/aeat/application/review/test_adapters.py`
- `src/aeat/entrypoints/cli/_ledger.py`
- `src/aeat/entrypoints/cli/test_workflow_surface.py`

## Tests

- `uv run pytest src/aeat/application/review/test_adapters.py src/aeat/application/review/test_aggregator.py src/aeat/entrypoints/cli/test_workflow_surface.py src/aeat/domain/transactions/test_repository.py -q`
