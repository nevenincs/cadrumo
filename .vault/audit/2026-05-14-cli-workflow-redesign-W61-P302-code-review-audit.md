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
  - '[[2026-05-13-cli-workflow-redesign-w61-p302-s1807-exec]]'
  - '[[2026-05-13-cli-workflow-redesign-w61-p302-s1808-exec]]'
  - '[[2026-05-13-cli-workflow-redesign-w61-p302-s1809-exec]]'
  - '[[2026-05-13-cli-workflow-redesign-w61-p302-s1810-exec]]'
  - '[[2026-05-13-cli-workflow-redesign-w61-p302-s1811-exec]]'
  - '[[2026-05-13-cli-workflow-redesign-w61-p302-s1812-exec]]'
---



# `cli-workflow-redesign` W61.P302 Code Review

No CRITICAL issues were found. HIGH issues are present and must be addressed before this phase should be treated as audit-clean.

W61.P302-001 | HIGH | Multiple canonical purchase-invoice evidence anchors are accepted
The ledger transaction ADR requires one canonical `purchase_invoice_evidence` anchor per transaction row, with a second canonical assignment rejected unless it is an explicit replacement. The implementation models canonical evidence as `purchase_invoice_evidence_ids: tuple[str, ...]` in `src/aeat/application/ledger/_models.py:52` and `src/aeat/domain/transactions/_models.py:397`, and the validator only rejects blanks or duplicates at `src/aeat/application/ledger/_models.py:95` and `src/aeat/domain/transactions/_models.py:485`. The contract test at `src/aeat/application/ledger/test_models.py:35` explicitly accepts two purchase evidence ids and asserts both survive at `src/aeat/application/ledger/test_models.py:45`. This violates the single-canonical-anchor invariant and leaves double-count prevention to downstream code after durable facts have already been persisted.

W61.P302-002 | HIGH | Manual ledger rows can persist unowned or non-existent evidence references
Manual transaction creation accepts raw evidence and attachment ids, then `_evidence_provenance` derives provenance entries from those strings at `src/aeat/application/ledger/_actions.py:239` through `src/aeat/application/ledger/_actions.py:257`. There is no lookup against `AttachmentStore`, no purchase-evidence manifest verification, and no bucket ownership check before `repository.save` persists the row at `src/aeat/application/ledger/_actions.py:71` or `src/aeat/application/ledger/_actions.py:164`. The positive service test uses the literal `evidence-1` at `src/aeat/application/ledger/test_actions.py:74` and only checks that this arbitrary id is copied into the transaction and provenance at `src/aeat/application/ledger/test_actions.py:96` through `src/aeat/application/ledger/test_actions.py:107`; the secure attachment test separately proves encrypted blob storage but never links that stored manifest to a ledger row. This means durable ledger facts can claim bucket-event-backed evidence provenance for evidence that is absent, outside the active bucket, or not stored through the secure evidence substrate.

W61.P302-003 | HIGH | Ledger mutations can commit without their mandatory bucket event history
Both manual create and update persist the transaction catalogue before appending the bucket event: create saves at `src/aeat/application/ledger/_actions.py:71` and appends at `src/aeat/application/ledger/_actions.py:72`; update saves at `src/aeat/application/ledger/_actions.py:164` and appends at `src/aeat/application/ledger/_actions.py:165`. `_append_bucket_event` performs a separate load and save at `src/aeat/application/ledger/_actions.py:406` through `src/aeat/application/ledger/_actions.py:407`, backed by a separate `BucketEventHistoryRepository.save` call. If event history persistence fails after the catalogue write, the bucket contains a manual transaction whose `created_event_id` or edit lineage points to an event that was never recorded. The ADR requires bucket event history to record manual creation and edits, so this needs a backend-owned atomic persistence boundary or compensating failure behavior that prevents unaudited ledger facts from becoming durable.

W61.P302-004 | HIGH | Manual update overwrites original creation provenance
`update_manual_transaction` preserves existing evidence provenance and edit lineage, but rebuilds the replacement transaction with the update command as the transaction's creation metadata. The replacement call passes the update event id at `src/aeat/application/ledger/_actions.py:152` through `src/aeat/application/ledger/_actions.py:162`, and `_transaction_from_command` writes `created_by`, `source_command`, and `created_event_id` directly from the current command at `src/aeat/application/ledger/_actions.py:211` through `src/aeat/application/ledger/_actions.py:213`. The update test checks only the appended edit lineage at `src/aeat/application/ledger/test_actions.py:207` through `src/aeat/application/ledger/test_actions.py:210`, so it misses that the original creator and create event are lost. A correction should preserve original creation provenance and add the correction actor/event only to update lineage.

W61.P302-005 | MEDIUM | Injected repositories can bypass the requested bucket boundary
The service defaults construct bucket-scoped repositories correctly, but injected repositories are accepted without checking that their `bucket_id` matches the command or requested bucket. Create and update use `transaction_repository or TransactionCatalogueRepository(bucket_id=command.bucket_id)` at `src/aeat/application/ledger/_actions.py:53` and `src/aeat/application/ledger/_actions.py:118`, then return refs for `command.bucket_id` at `src/aeat/application/ledger/_actions.py:73` and `src/aeat/application/ledger/_actions.py:166`. Get and list similarly accept a `bucket_id` argument but return results for `repository.bucket_id` when a repository is injected at `src/aeat/application/ledger/_actions.py:84` through `src/aeat/application/ledger/_actions.py:104`. A backend caller or test harness can therefore persist or read rows from one bucket while events and returned refs name another bucket. The application boundary should fail closed on repository-command bucket mismatches.

W61.P302-006 | LOW | Verification passed but missed the audit-critical failure modes above
The targeted review command `uv run --no-sync pytest src/aeat/application/ledger/test_models.py src/aeat/application/ledger/test_actions.py src/aeat/domain/transactions/test_models.py src/aeat/domain/transactions/test_repository.py src/aeat/domain/attachments/test_repository.py src/aeat/application/review/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/application/aggregation/test_renta_ledger.py -q` passed with 50 tests. `uv run --no-sync ty check src/aeat/application/ledger src/aeat/domain/transactions src/aeat/domain/attachments/_models.py src/aeat/application/review src/aeat/entrypoints/cli/_ledger.py` also passed. The gaps are behavioral: no test rejects a second canonical purchase evidence anchor, no test proves evidence ids are real secure bucket objects, no test simulates event-history persistence failure after a ledger write, no test preserves creation provenance across update, and no test rejects repository bucket mismatch injection.
