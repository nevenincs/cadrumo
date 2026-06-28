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



# `cli-workflow-redesign` W61.P302 Bucket Ownership Re-Review

No CRITICAL or HIGH issues were found in this re-review. `W61.P302-002` is resolved for the reviewed surface: manual ledger evidence verification now requires purchase invoice evidence and secure attachment manifests to carry the same bucket as the `ManualLedgerTransactionCommand` before the transaction catalogue is saved.

`W61.P302-002` | RESOLVED | Manual ledger evidence references are now bucket-owned
The prior HIGH was open because manual ledger rows could claim globally stored purchase invoice evidence or attachment manifests without proving ownership by the active profile bucket. The current implementation adds `Invoice.bucket_id` and `Attachment.bucket_id`, normalizes those fields at model boundaries, and `_verify_evidence_references` rejects any `purchase_invoice_evidence_id` or `attachment_ids` entry whose stored `bucket_id` differs from `command.bucket_id`. For purchase evidence, the verifier still requires an existing invoice and `InvoiceKind.RECEIVED`. For attachments, the verifier still requires the manifest, verifies the blob digest, enforces `Attachment.bucket_id == command.bucket_id`, and then applies the existing linked-transaction guard. Legacy evidence with no `bucket_id` is fail-closed because `None != command.bucket_id`.

`W61.P302-R006` | MEDIUM | Event and catalogue writes still have inverse drift risk
The original HIGH failure mode of a durable manual transaction with no event history remains closed because create and update both call `_append_bucket_event` before `TransactionCatalogueRepository.save`. The inverse drift still applies: `_append_bucket_event` and `TransactionCatalogueRepository.save` are separate repository writes with no shared SQL transaction, backend-owned atomic boundary, or compensating delete. If event history saves successfully and the later transaction catalogue save fails, bucket event history can contain `ledger_transaction.created` or `ledger_transaction.updated` for a row that did not persist.

`W61.P302-T001` | LOW | Attachment cross-bucket rejection lacks a direct regression test
The implementation enforces attachment bucket ownership in `_verify_evidence_references`, and the manual ledger test suite covers cross-bucket rejection for purchase invoice evidence. The reviewed tests do not include an equivalent manual-ledger action test that writes an attachment manifest for `bucket-b` and proves a `bucket-a` command rejects it. This is a coverage gap, not a reopened HIGH, because the production verifier has the exact attachment ownership check.

## Prior Finding Disposition

- `W61.P302-002`: Resolved. Existence, received-invoice type, blob integrity, and bucket ownership are enforced before durable manual ledger facts claim evidence provenance.
- `W61.P302-R006`: Still open at MEDIUM. Event-first ordering prevents durable ledger rows without events, but does not make event and transaction catalogue persistence atomic in the inverse direction.

## Verification Commands

- `uv run --no-sync pytest src/aeat/application/ledger/test_models.py src/aeat/application/ledger/test_actions.py src/aeat/domain/transactions/test_models.py src/aeat/domain/transactions/test_repository.py src/aeat/domain/attachments/test_repository.py src/aeat/domain/invoices/test_models.py -q`
  - Result: passed, 57 tests.
- `uv run --no-sync ty check src/aeat/application/ledger src/aeat/domain/transactions src/aeat/domain/attachments/_models.py src/aeat/domain/attachments/_repository.py src/aeat/domain/invoices/_models.py`
  - Result: passed, `All checks passed!`.
- `rg -n "invoice\\.bucket_id|attachment\\.bucket_id|linked_transaction_ids|purchase_invoice_evidence_id must belong|attachment_ids must belong" src/aeat/application/ledger/_actions.py src/aeat/application/ledger/test_actions.py src/aeat/domain/attachments/_models.py src/aeat/domain/invoices/_models.py`
  - Result: confirmed ownership checks in `_verify_evidence_references`, `Attachment.bucket_id`, `Invoice.bucket_id`, and the remaining linked-transaction guard.

## Reviewed Surface

The re-review read the previous W61.P302 remediation audit, the manual ledger storage ADR, the manual ledger application services and tests, the transaction domain models and repository tests, the attachment model and repository, the invoice model and invoice model tests, and the bucket event and secure object persistence paths relevant to event/catalogue ordering.
