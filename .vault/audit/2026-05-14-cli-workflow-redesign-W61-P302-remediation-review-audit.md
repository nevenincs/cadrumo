---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-w61-p302-s1807-exec]]'
  - '[[2026-05-13-cli-workflow-redesign-w61-p302-s1808-exec]]'
  - '[[2026-05-13-cli-workflow-redesign-w61-p302-s1809-exec]]'
  - '[[2026-05-13-cli-workflow-redesign-w61-p302-s1810-exec]]'
  - '[[2026-05-13-cli-workflow-redesign-w61-p302-s1811-exec]]'
  - '[[2026-05-13-cli-workflow-redesign-w61-p302-s1812-exec]]'
---



# `cli-workflow-redesign` W61.P302 Remediation Code Review

HIGH issue remains. Four of the five prior findings are resolved for their original failure mode; `W61.P302-002` is only partially remediated and remains open because evidence existence is now checked but evidence ownership is still not bucket-scoped.

W61.P302-002 | HIGH | Still open: manual ledger evidence references are not bucket-owned
The remediation added real existence checks before manual transaction persistence: `_verify_evidence_references` loads the purchase invoice catalogue for `purchase_invoice_evidence_id` and requires `InvoiceKind.RECEIVED`; it also loads each attachment manifest and verifies the stored blob. This closes the prior "non-existent evidence id" path. It does not close the "unowned evidence" path. `InvoiceCatalogueRepository` still persists one global catalogue under `_INVOICE_NAMESPACE = "aeat.domain.invoices"` and `_INVOICE_OBJECT_KEY = "catalogue"`, with no `bucket_id` constructor argument or object key partitioning. `AttachmentStore` likewise uses global blob and manifest namespaces, and `Attachment` has `linked_transaction_ids`, `linked_invoice_ids`, `captured_by`, and `source_command`, but no owning bucket field. The ledger verifier only rejects an attachment when `linked_transaction_ids` is non-empty and does not include the new transaction id; an attachment with no linked transactions can be claimed by any bucket. The manual ledger ADR requires manual ledger transactions to persist under the active profile bucket, and the prior audit specifically required bucket ownership checks before durable facts claim evidence provenance. Manual rows can therefore still attach globally stored invoice evidence or globally stored secure attachments that belong to another profile bucket.

W61.P302-R006 | MEDIUM | New residual: event and catalogue writes still have no atomic persistence boundary
The prior "transaction committed without event history" failure mode is resolved by ordering `_append_bucket_event` before `repository.save` in both create and update. However, the inverse inconsistency remains: if the bucket event repository saves successfully and the transaction catalogue save then fails, bucket event history will contain `ledger_transaction.created` or `ledger_transaction.updated` for a transaction row that did not persist. The reviewed code still uses separate repository writes with no shared backend-owned transaction or compensating delete. This is lower severity than the original HIGH because the unaudited ledger fact is no longer durable, but event history can still drift from catalogue truth.

## Prior Finding Disposition

- `W61.P302-001`: Resolved. `ManualLedgerTransactionCommand` and `Transaction` now expose singular `purchase_invoice_evidence_id` fields, and `test_manual_ledger_transaction_command_rejects_multi_purchase_evidence_value` proves tuple input is rejected.
- `W61.P302-002`: Still open at HIGH. Existence checks were added, but bucket ownership remains absent for purchase invoice evidence and attachment manifests.
- `W61.P302-003`: Resolved for the original HIGH. Create and update now append the bucket event before saving the transaction catalogue, and `test_create_manual_transaction_does_not_save_transaction_when_event_history_fails` proves event-history failure prevents transaction persistence.
- `W61.P302-004`: Resolved. `update_manual_transaction` preserves `created_by`, `source_command`, and `created_event_id` from the current transaction, and the update test asserts those fields survive correction.
- `W61.P302-005`: Resolved. `_transaction_repository` now rejects injected `TransactionCatalogueRepository` instances whose `bucket_id` differs from the command or requested bucket, and `test_create_manual_transaction_rejects_repository_bucket_mismatch` covers the create path. Get and list route through the same helper.

## Verification Commands

- `uv run --no-sync pytest src/aeat/application/ledger/test_models.py src/aeat/application/ledger/test_actions.py src/aeat/domain/transactions/test_models.py src/aeat/domain/transactions/test_repository.py src/aeat/domain/attachments/test_repository.py src/aeat/application/review/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/application/aggregation/test_renta_ledger.py -q`
  - Result: passed, 55 tests.
- `uv run --no-sync ty check src/aeat/application/ledger src/aeat/domain/transactions src/aeat/domain/attachments/_models.py src/aeat/domain/attachments/_repository.py src/aeat/application/review src/aeat/entrypoints/cli/_ledger.py`
  - Result: passed, `All checks passed!`.

## Reviewed Surface

The review read the prior audit, the W61 epic plan rows, the manual ledger storage ADR, W61.P302 execution records, and the changed implementation surface in `src/aeat/application/ledger`, `src/aeat/domain/transactions`, `src/aeat/domain/attachments/_repository.py`, `src/aeat/domain/attachments/_models.py`, `src/aeat/application/review`, and `src/aeat/entrypoints/cli/_ledger.py`.
