---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P304.S1820'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-14-cli-workflow-redesign-w61-p304-s1820-code-review-audit]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-ledger-transaction-removal-adr]]"
---

# `cli-workflow-redesign` `W61.P304.S1820`

Closed plan rows:

- `W61.P304.S1820`

## Description

Implemented bucket event emission for the real ledger backend mutation paths currently present in the codebase. Manual transaction creation, provider import, and manual transaction update now emit durable bucket events through the ledger application service without storing ledger mutations in review overlays or adding placeholder services for later rows.

The implemented event vocabulary uses dotted ledger event values, including `ledger.transaction.created`, `ledger.transaction.imported`, `ledger.transaction.updated`, `ledger.transaction.classified`, and `ledger.transaction.allocated`. The taxonomy also covers semantic `purchase_invoice_evidence` and attachment events needed by later workflow rows while preserving `purchase_invoice_evidence`, `payable_invoice`, and `collectible_invoice` terminology.

`create_manual_transaction` persists the manual transaction and emits `ledger.transaction.created` through `_save_transaction_catalogue_and_events`. The transaction catalogue row and event history are saved in one secure-object unit of work.

`import_ledger_transactions` imports only new provider `RawTransaction` rows, skips duplicates, emits one `ledger.transaction.imported` event for each imported row, and returns `bucket_event_ids`.

`update_manual_transaction` replaces the catalogue row and emits semantic events for edit, classify, allocate, `purchase_invoice_evidence` attach, replace, and detach, plus attachment link and remove operations.

Mixed edit-plus-evidence lineage is explicit. Edit lineage uses the primary ledger transaction event, while evidence provenance maps to the specific evidence or attachment event.

CLI import delegates to `import_ledger_transactions` and includes `bucket_event_ids` in JSON output. The legacy CLI review edit mutation path is refused rather than storing ledger mutations in review overlays.

Remove, reset, archive, and export operation implementations remain subsequent plan rows. S1820 covers the current real backend mutation paths and the event taxonomy those later rows need.

`SecureObjectWrite` and `SecureObjectRepository.save_many` now allow multiple secure-object upserts in one SQL `session_scope` unit of work. `TransactionCatalogueRepository.save_with_secure_object_writes` persists the transaction catalogue plus related event-history write atomically through secure-object storage. `BucketEventHistoryRepository.to_secure_object_write` prepares event-history writes without committing separately.

The S1820 audit found no HIGH or CRITICAL issues. Initial MEDIUM findings were resolved: false event-history drift is closed by `save_many` and combined writes for create, import, and update paths; mixed evidence provenance now points to the specific semantic evidence or attachment event.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P304-S1820-code-review-audit.md`
- `src/aeat/adapters/persistence/storage/sql/secure_objects.py`
- `src/aeat/adapters/persistence/storage/sql/__init__.py`
- `src/aeat/domain/transactions/_repository.py`
- `src/aeat/domain/buckets/_event.py`
- `src/aeat/domain/buckets/_event_repository.py`
- `src/aeat/domain/buckets/test_event_catalogue.py`
- `src/aeat/application/ledger/_actions.py`
- `src/aeat/application/ledger/_models.py`
- `src/aeat/application/ledger/__init__.py`
- `src/aeat/application/ledger/test_actions.py`
- `src/aeat/entrypoints/cli/_ledger.py`
- `src/aeat/entrypoints/cli/test_workflow_surface.py`

## Tests

- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/__init__.py src/aeat/domain/transactions/_repository.py src/aeat/domain/buckets/_event_repository.py src/aeat/application/ledger/_actions.py src/aeat/application/ledger/_models.py src/aeat/application/ledger/__init__.py src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_workflow_surface.py src/aeat/domain/buckets/_event.py src/aeat/domain/buckets/test_event_catalogue.py`
  - All checks passed
- `uv run --no-sync ty check src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/__init__.py src/aeat/domain/transactions/_repository.py src/aeat/domain/buckets/_event_repository.py src/aeat/application/ledger/_actions.py src/aeat/application/ledger/_models.py src/aeat/application/ledger/__init__.py src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_workflow_surface.py src/aeat/domain/buckets/_event.py src/aeat/domain/buckets/test_event_catalogue.py`
  - All checks passed
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/entrypoints/cli/test_workflow_surface.py src/aeat/application/transactions/test_import.py src/aeat/domain/transactions/test_repository.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q`
  - 85 passed

Coverage includes create/import/update ledger event emission, duplicate-import no-event behavior, CLI import event output, semantic edit/classify/allocate events, `purchase_invoice_evidence` attachment events, mixed edit-plus-evidence lineage, legacy underscore event rejection, secure-object event/catalogue combined writes, and existing transaction import/repository behavior.
