---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-libros-boe-format-exporters-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]'
---



# `cli-workflow-redesign` Code Review



W61-P304-S1823-001 | HIGH | Ledger export events fail for ordinary multi-row catalogues

`export_ledger_transactions` builds a `ledger.transaction.exported` bucket event whose payload includes `transaction_ids` as one comma-separated string. Bucket event payload values are capped at 500 characters by the `BucketEvent` contract, while eight 64-character transaction ids plus separators exceed that limit. As a result, exporting a bucket with eight or more rows raises during `BucketEvent` construction before `_save_transaction_catalogue_and_events` can persist the export event atomically. This breaks the backend-only S1823 export path for realistic bucket-scoped catalogues even though the serializer and row projection are otherwise canonical and bucket-local. Replace the unbounded list payload with bounded metadata, such as a count plus digest, or persist row identifiers through a versioned export artifact/event detail contract. Add a non-tautological test that creates enough real bucket-scoped ledger transactions to cross the event payload limit and asserts export succeeds with a persisted `ledger.transaction.exported` event whose `object_type` is `ledger_export`.

Review notes:

- No `CRITICAL` issues found.
- One `HIGH` issue remains.
- The reviewed export path stays backend-only and does not add CLI business logic.
- No filing/modelo export path or legacy review shim is used by the S1823 export implementation.
- The observed row projection uses the canonical bucket-bound `TransactionCatalogueRepository`, filters inactive lifecycle states by default, orders rows deterministically by effective date and transaction id, and returns digest and byte metadata.
- Existing tests cover active-row export, inactive filtering, bucket scoping, event taxonomy, CSV and JSONL serialization, and real SQL-backed secure-object persistence, but they do not cover the event payload size boundary above.

Re-review notes after HIGH remediation:

- `W61-P304-S1823-001` is resolved. `export_ledger_transactions` no longer stores an unbounded comma-separated `transaction_ids` payload value for `ledger.transaction.exported`.
- The export event payload now records bounded metadata: `row_count`, `byte_size`, export `sha256`, `transaction_ids_sha256`, and first / last transaction ids. The only command-sourced strings in that payload are constrained by `LedgerExportCommand`, and transaction id / digest values are fixed at 64 characters, so the bucket-event 500-character payload-value cap is respected by construction.
- The added large-export test creates real bucket-scoped ledger transactions, exports 12 rows, asserts `transaction_ids` is absent from the persisted event payload, checks the 64-character transaction-id digest, and verifies all event payload values stay within 500 characters.
- I did not identify any new `HIGH` or `CRITICAL` issues in the reviewed files.
