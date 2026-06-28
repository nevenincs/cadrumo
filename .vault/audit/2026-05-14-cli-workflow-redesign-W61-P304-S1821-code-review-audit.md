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

W61-P304-S1821-001 | HIGH | Editing an archived or stashed transaction silently reactivates it and drops lifecycle lineage
`update_manual_transaction` builds replacement rows through `_transaction_from_command` twice, passing existing creation, evidence, and edit lineage, but never passing the current `lifecycle_state` or `lifecycle_lineage`. `_transaction_from_command` then constructs a fresh `Transaction` payload without lifecycle fields, so Pydantic defaults the replacement to `ACTIVE` with an empty lifecycle chain. Because `_replace_transaction` removes the old row and stores the replacement under the new or existing transaction id, any later edit of an archived or stashed row can erase the durable archive/stash state and its bucket-event lineage without emitting an unarchive/unstash event. This violates S1821's requirement that archive/stash be durable transaction substrate state rather than a review overlay, and it weakens the bucket-event ADR's auditability contract because the catalogue no longer agrees with the already persisted `ledger.transaction.archived` or `ledger.transaction.stashed` history. The update path should either reject edits to non-`ACTIVE` rows until an explicit lifecycle transition exists, or preserve lifecycle state and lineage across ordinary edits with regression coverage for archived and stashed rows.

W61-P304-S1821-002 | HIGH | Archived and stashed rows still feed active ledger aggregation and preflight paths
The new lifecycle state is persisted on `Transaction`, but active ledger readers do not consult it. `list_manual_transactions` returns every catalogue row, `preflight_transaction_catalogue` checks every in-period row from `transactions.values()`, and both `aggregate_renta_ledger_expenses` and `aggregate_iva_ledger_observations` iterate every transaction without excluding or blocking `ARCHIVED` and `STASHED` rows. A transaction archived as a wrong-account import, or stashed because it is not ready, can therefore still be counted in Renta/IVA observations and modelo-readiness checks if its other tax fields are complete. That makes archive/stash a label rather than an effective backend lifecycle state for downstream workflow, and conflicts with the manual-ledger ADR's requirement that archive state be a durable transaction fact consumed by model preparation. The lifecycle contract should be enforced at the canonical catalogue query/projection boundary or in each active workflow consumer, with tests proving archived/stashed rows do not contribute to active aggregation/preflight output unless an explicit include/history mode is requested.

No CRITICAL issues found. HIGH issues were found and are listed above.

Review notes:

- No `aeat app archive` or root archive CLI exposure was added by the reviewed implementation. `aeat.application.archive` is an internal package that re-exports ledger services and explicitly states it is not an operator CLI root.
- Archive/stash events use the approved `ledger.transaction.archived` and `ledger.transaction.stashed` vocabulary and are persisted through `_save_transaction_catalogue_and_events`, which uses the combined transaction catalogue plus bucket-event secure-object save helper from S1820.
- Bucket-scoped repository mismatch protection is reused for archive/stash through `_transaction_repository`, so injected repositories whose `bucket_id` does not match the command bucket are rejected before mutation.
- `TransactionLifecycleState` and `TransactionLifecycleLineageEntry` are strict frozen Pydantic models, parse JSON strings back to closed enum/datetime types, reject blank actor/source/event fields, and reject noop lifecycle transitions.
- Tests cover JSON round-trip, noop lifecycle rejection, archive/stash event and lineage persistence, invalid archive/stash transition refusal, and preservation of event history on refused transitions. They do not cover editing non-active rows or aggregation/preflight behavior for non-active rows.

Verification observed from the implementation handoff:

- `uv run --no-sync ruff check src/aeat/domain/transactions/_enums.py src/aeat/domain/transactions/_models.py src/aeat/domain/transactions/__init__.py src/aeat/domain/transactions/test_models.py src/aeat/application/ledger/_actions.py src/aeat/application/ledger/__init__.py src/aeat/application/ledger/test_actions.py src/aeat/application/archive/__init__.py src/aeat/domain/buckets/_event.py src/aeat/domain/buckets/test_event_catalogue.py`
- `uv run --no-sync ty check ...same files...`
- `uv run --no-sync pytest src/aeat/domain/transactions/test_models.py src/aeat/application/ledger/test_actions.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q`

Additional review verification:

- No files were modified other than this requested audit document.
- I did not rerun the test suite during review.

Re-review 2026-05-14:

W61-P304-S1821-RR-001 | LOW | Prior HIGH remediation verified; no remaining HIGH or CRITICAL issues found
The two prior HIGH findings are resolved in the reviewed remediation. `update_manual_transaction` now refuses non-`ACTIVE` transactions before constructing a replacement row, so archived or stashed rows cannot be silently reactivated by edit/classify/allocate/attach paths. The same replacement construction also preserves `lifecycle_state` and `lifecycle_lineage` for ordinary active-row edits, keeping durable transaction state aligned with bucket-event lineage. `aggregate_iva_ledger_observations`, `aggregate_renta_ledger_expenses`, and `preflight_transaction_catalogue` now skip non-active rows before producing observations, casilla values, prorrata references, or readiness blockers. Repository-backed aggregation and preflight paths still enforce bucket-id matching before loading catalogues.

No new HIGH or CRITICAL issues were found in the re-review scope. The remediation keeps lifecycle transitions in backend application services, persists transaction catalogue and bucket-event history through the combined secure-object write helper, and does not add a user-facing `archive` CLI root or CLI-local archive/stash business logic. The focused tests are not vacuous for the reviewed defects: they exercise persisted lifecycle state and event ids, edit refusal without catalogue/event mutation, and active-only IVA/Renta/preflight projections with inactive rows present.

Verification commands executed during re-review:

- `uv run --no-sync ruff check src/aeat/application/ledger/_actions.py src/aeat/application/ledger/test_actions.py src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/aggregation/_renta_ledger.py src/aeat/application/aggregation/test_renta_ledger.py src/aeat/application/ledger/_preflight.py src/aeat/application/ledger/test_preflight.py src/aeat/domain/transactions/_enums.py src/aeat/domain/transactions/_models.py src/aeat/domain/transactions/__init__.py src/aeat/domain/transactions/test_models.py src/aeat/application/archive/__init__.py src/aeat/domain/buckets/_event.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` - passed
- `uv run --no-sync ty check src/aeat/application/ledger/_actions.py src/aeat/application/ledger/test_actions.py src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/aggregation/_renta_ledger.py src/aeat/application/aggregation/test_renta_ledger.py src/aeat/application/ledger/_preflight.py src/aeat/application/ledger/test_preflight.py src/aeat/domain/transactions/_enums.py src/aeat/domain/transactions/_models.py src/aeat/domain/transactions/__init__.py src/aeat/domain/transactions/test_models.py src/aeat/application/archive/__init__.py src/aeat/domain/buckets/_event.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` - passed
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/aggregation/test_renta_ledger.py src/aeat/application/ledger/test_preflight.py src/aeat/domain/transactions/test_models.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -q` - 95 passed
