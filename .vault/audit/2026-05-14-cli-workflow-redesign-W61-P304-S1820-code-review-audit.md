---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-ledger-transaction-removal-adr]]'
---

# `cli-workflow-redesign` Code Review

No HIGH or CRITICAL issues found.

W61-P304-S1820-001 | MEDIUM | Bucket events can be persisted without the matching ledger catalogue mutation
`import_ledger_transactions` appends bucket events before saving the imported transaction catalogue, and `update_manual_transaction` follows the same order for edit events before replacing the catalogue row. `BucketEventHistoryRepository.save` and `TransactionCatalogueRepository.save` each perform an independent secure-object upsert, so a later catalogue save failure leaves durable bucket history claiming an import/update/classification/allocation/attachment occurred even though the ledger row was not persisted. This violates the bucket-event ADR's requirement to write events in the same logical transaction as the domain state change where storage allows it, and creates audit history that can no longer be reconciled to current state. The affected ordering is visible in `import_ledger_transactions` around the event append followed by `repository.save`, and in `update_manual_transaction` around the event append followed by `_replace_transaction` persistence. The remediation should persist the ledger state and event history through one storage transaction/unit-of-work, or otherwise add an explicit compensating design and tests that prove partial writes cannot leave false positive bucket events.

W61-P304-S1820-002 | MEDIUM | Mixed edit-plus-attach operations can point evidence provenance at the wrong semantic event
`update_manual_transaction` builds all semantic events first, then computes one `primary_event_id` by returning the first event whose object type is `ledger_transaction`. When an update changes a core/classification/allocation field and also attaches or replaces evidence, the first ledger transaction event wins, and `_transaction_from_command` passes that same event id into `_evidence_provenance` for every newly linked purchase evidence or attachment. The persisted evidence provenance can therefore reference `ledger.transaction.updated`, `ledger.transaction.classified`, or `ledger.transaction.allocated` instead of the actual `purchase_invoice_evidence.attached/replaced` or `attachment.linked` event emitted later in the same operation. Evidence-only attach tests pass because the evidence event is the only event, but mixed changes are not covered. This weakens the event lineage operators need for attach history and directly touches the review focus around semantic event classification for mixed changes. The update path should map each newly added evidence/attachment id to its own emitted event id, while keeping edit lineage tied to the primary ledger transaction event.

Review notes:

- CLI import now delegates persistence and event emission to `import_ledger_transactions`; no new CLI-local merge or event-construction business logic was found in the reviewed import path.
- Repository mismatch safety exists in the ledger application boundary: injected transaction repositories whose `bucket_id` differs from the command/import bucket are rejected before mutation.
- No legacy ledger event aliases or compatibility shims were found; the event enum uses the approved `ledger.transaction.*` vocabulary and the tests reject legacy underscore transaction event strings.
- The reviewed S1820 implementation does not add remove/reset/archive/export placeholder services; event vocabulary for those future operations remains enum-only from S1819/S1820 catalogue scope.
- Tests exercise real secure-object repositories and bucket event repositories rather than mocks. The main gap is the missing failure/partial-persistence coverage and missing mixed edit-plus-evidence provenance coverage described above.

Verification observed from the implementation handoff:

- `uv run --no-sync ruff check src/aeat/application/ledger/_actions.py src/aeat/application/ledger/_models.py src/aeat/application/ledger/__init__.py src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_workflow_surface.py src/aeat/domain/buckets/_event.py src/aeat/domain/buckets/test_event_catalogue.py`
- `uv run --no-sync ty check src/aeat/application/ledger/_actions.py src/aeat/application/ledger/_models.py src/aeat/application/ledger/__init__.py src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_workflow_surface.py src/aeat/domain/buckets/_event.py src/aeat/domain/buckets/test_event_catalogue.py`
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/entrypoints/cli/test_workflow_surface.py src/aeat/application/transactions/test_import.py src/aeat/domain/transactions/test_repository.py -q`

Resolution note, 2026-05-14:

- W61-P304-S1820-001 remains partially unresolved. The remediation adds `SecureObjectWrite`, `SecureObjectRepository.save_many(...)`, `TransactionCatalogueRepository.save_with_secure_object_writes(...)`, and `BucketEventHistoryRepository.to_secure_object_write(...)`, and `import_ledger_transactions` plus `update_manual_transaction` now persist the ledger catalogue and bucket-event-history catalogue through one `save_many` unit of work. That closes the originally reviewed import/update split-save path. However, `create_manual_transaction` still calls `_append_bucket_event(...)` before `repository.save(...)`, so a transaction catalogue save failure after the event-history save can still leave a durable `ledger.transaction.created` event without the matching ledger row. The MEDIUM issue therefore remains open for the create path.
- W61-P304-S1820-002 is resolved. `update_manual_transaction` now derives an evidence-id to event-id map from the emitted semantic evidence/attachment events and passes it into transaction construction. Newly created `purchase_invoice_evidence` and `attachment` provenance entries use the matching evidence or attachment event id, while edit lineage remains tied to the primary ledger transaction event. `test_update_manual_transaction_mixed_edit_and_evidence_lineage_uses_evidence_event` covers the mixed edit-plus-evidence regression case.
- No HIGH or CRITICAL issues were found in this re-review.

Final resolution note, 2026-05-14:

- W61-P304-S1820-001 is resolved. `create_manual_transaction` now calls `_save_transaction_catalogue_and_events(...)` with the upserted transaction catalogue and the created bucket event, matching the import and update paths. The helper builds the bucket-event-history catalogue write and persists it with the transaction catalogue through `TransactionCatalogueRepository.save_with_secure_object_writes(...)`.
- The reviewed persistence path now reaches `SecureObjectRepository.save_many(...)`, which performs the transaction catalogue upsert and event-history upsert inside one SQL `session_scope` unit of work. I did not find a remaining split-save path for the reviewed manual create/import/update ledger-event writes.
- No HIGH or CRITICAL issues remain in this final narrow re-review.
