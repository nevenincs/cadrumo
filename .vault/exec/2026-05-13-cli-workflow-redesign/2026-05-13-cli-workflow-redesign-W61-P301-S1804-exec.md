---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W61.P301.S1804'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-w61-p301-s1801-ledger-storage-ownership-audit]]"
---

# `cli-workflow-redesign` `W61.P301.S1804`

Closed plan rows:

- `W61.P301.S1804`

## Description

Implemented the per-bucket transaction identity contract for imported ledger rows.

The content-derived `transaction_id` remains stable and idempotent inside one transaction catalogue. Cross-profile references are now represented with the strict Pydantic `BucketTransactionRef` record, which qualifies every transaction id with its owning profile bucket id. `ImportSummary` carries `bucket_id`, `imported_refs`, and `skipped_refs`, so backend callers and CLI renderers can report transaction identities without treating `transaction_id` as globally unique.

`TransactionCatalogueRepository.merge_raw_transactions` now builds imported and skipped refs from the repository's bound bucket id. The CLI import JSON payload renders those backend refs directly and does not infer bucket scope in the command layer.

Added repository coverage over the real encrypted SQL object backend. The test imports the same raw row into two profile buckets, verifies both buckets import it independently with the same content-derived transaction id, and verifies a repeat import into the first bucket is skipped only inside that bucket.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `src/aeat/domain/transactions/_models.py`
- `src/aeat/domain/transactions/_repository.py`
- `src/aeat/domain/transactions/__init__.py`
- `src/aeat/domain/transactions/test_repository.py`
- `src/aeat/entrypoints/cli/_ledger.py`

## Tests

- `uv run pytest src/aeat/domain/transactions/test_repository.py src/aeat/domain/transactions/test_catalogue.py src/aeat/application/workflow/test_transaction_catalogue_resolution.py src/aeat/entrypoints/cli/test_workflow_surface.py -q`
