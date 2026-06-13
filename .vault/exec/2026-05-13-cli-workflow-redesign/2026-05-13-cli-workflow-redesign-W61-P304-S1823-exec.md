---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P304.S1823'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-14-cli-workflow-redesign-w61-p304-s1823-code-review-audit]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-libros-boe-format-exporters-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
---

# `cli-workflow-redesign` `W61.P304.S1823`

Closed plan rows:

- `W61.P304.S1823`

## Description

Implemented the backend-only ledger transaction export path for canonical bucket-scoped ledger rows. S1823 exports `ledger_transaction` movement facts from the bucket-local transaction catalogue; it is not a modelo export, filing export, live AEAT submission path, review queue export, or BOE libro-registro exporter.

`LedgerExportCommand` now identifies the bucket and requested tabular format. `export_ledger_transactions` loads the bucket-scoped `TransactionCatalogueRepository`, projects canonical `LedgerExportRow` records, serializes them through the shared application tabular serializer, emits one `ledger.transaction.exported` bucket event with `ledger_export` object type, and returns `LedgerExportResult`.

The default export includes only `ACTIVE` ledger transactions. `include_inactive=True` includes inactive lifecycle rows such as `STASHED`. Export row ordering is deterministic by effective date, using `value_date` when present and `booked_date` otherwise, then by `transaction_id`.

The shared `application.export` tabular serializer supports `csv` and `jsonl` output. Export metadata includes row count, byte size, SHA-256 digest, media type, filename extension, field names, payload bytes, projected rows, and bucket event ids.

The initial S1823 review found one HIGH issue: the export event payload stored an unbounded comma-separated `transaction_ids` value, which could exceed the bucket event 500-character payload-value cap. The implementation now stores bounded metadata: row count, byte size, export digest, `transaction_ids_sha256`, first transaction id, and last transaction id. Re-review found no remaining HIGH or CRITICAL issues.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P304-S1823-code-review-audit.md`
- `src/aeat/application/export/__init__.py`
- `src/aeat/application/export/_tabular.py`
- `src/aeat/application/export/test_tabular.py`
- `src/aeat/application/ledger/__init__.py`
- `src/aeat/application/ledger/_actions.py`
- `src/aeat/application/ledger/_models.py`
- `src/aeat/application/ledger/test_actions.py`

## Tests

- `uv run --no-sync ruff check src/aeat/application/export src/aeat/application/ledger/_models.py src/aeat/application/ledger/_actions.py src/aeat/application/ledger/__init__.py src/aeat/application/ledger/test_actions.py`
  - All checks passed
- `uv run --no-sync ty check src/aeat/application/export src/aeat/application/ledger/_models.py src/aeat/application/ledger/_actions.py src/aeat/application/ledger/__init__.py src/aeat/application/ledger/test_actions.py`
  - All checks passed
- `uv run --no-sync pytest src/aeat/application/export/test_tabular.py src/aeat/application/ledger/test_actions.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q`
  - 62 passed

Coverage includes deterministic CSV and JSONL serialization, unknown-field rejection, bucket-isolated ledger export, active-row filtering, inactive-row opt-in, export ordering, digest and metadata reporting, `ledger.transaction.exported` event emission, and bounded event payload behavior for larger exports.
