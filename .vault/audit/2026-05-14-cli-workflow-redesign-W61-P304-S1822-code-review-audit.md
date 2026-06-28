---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-ledger-transaction-removal-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]'
---

# `cli-workflow-redesign` Code Review

S1822-001 | CRITICAL | Finalized modelo deletion guard can be bypassed because ledger transaction ids are still content-derived and mutable.

`CalculationRevision.source_transaction_ids` is now the only persisted citation set used by `_blocking_modelo_references`, but the cited id is not durable enough for the guard. `derive_transaction_id` hashes mutable row facts (`amount`, `description`, and effective date) plus provider id. `update_manual_transaction` rebuilds the row from the replacement command and then `_replace_transaction` removes the old key and inserts the replacement key; it does not call `_blocking_modelo_references` before doing so. A verified/filed revision that cites transaction id `A` can therefore be followed by an edit that changes amount, description, value date, or idempotency key and replaces the catalogue entry with id `B`. After that, `remove_manual_transaction` checks only `B`, and `reset_ledger_catalogue` checks only the currently present ids, so the verified/filed revision's citation to `A` no longer blocks physical deletion of the ledger row's successor. This violates the S1822 requirement that removal/reset must not delete transactions cited by verified/filed revisions and the explicit review focus that source transaction ids must be durable enough for that guard. The fix needs either immutable bucket-local transaction identity for modelo source refs, or finalized-revision blockers on every mutation path that can change or remove a cited transaction id, including edit/archive/stash if they make the cited row unavailable to aggregation.

Relevant code: `src/aeat/domain/transactions/_models.py` lines 38-60, `src/aeat/domain/modelos/_calculation_revision.py` lines 191 and 266-284, `src/aeat/application/ledger/_actions.py` lines 446-543 and 643-663.

S1822-002 | HIGH | Ledger reset deletes all bucket transactions without applying the dependency cascade required for physical removal.

`remove_manual_transaction` detaches bucket-local purchase invoice evidence and emits `purchase_invoice_evidence.detached` plus `ledger.transaction.removed` events before deleting one transaction. `reset_ledger_catalogue` performs the same class of physical deletion in bulk, but it only writes an empty `TransactionCatalogue()` and emits one `ledger.catalogue.reset` event. It does not load or update the invoice catalogue, detach `linked_transaction_ids`, emit `purchase_invoice_evidence.detached` events, report affected evidence ids, or handle other dependent ledger links/review state. After a reset, purchase evidence can still point at transaction ids that no longer exist in the bucket catalogue, leaving orphaned evidence links that the ledger-management ADR treats as blockers rather than acceptable residual state. This is also an event-taxonomy gap: the only durable history is the catalogue reset summary, not the per-dependent-object events that single-row physical removal records.

Relevant code: `src/aeat/application/ledger/_actions.py` lines 247-335, 338-404, and 703-783.

Verification noted from implementer:

- `ruff` passed.
- `ty` passed.
- `pytest` reported 73 passed for the ledger/bucket/reset slice.
- `pytest` reported 37 passed for the modelo file/amend/import flow.

S1822-RR-001 | LOW | Reset finalized-reference refusal is fixed in code but lacks a direct regression test.

Re-review found no remaining HIGH or CRITICAL blocker in the reviewed S1822 slice. The prior S1822-001 guard is now applied to `update_manual_transaction`, archive/stash lifecycle transitions, `remove_manual_transaction`, and `reset_ledger_catalogue`; `_transaction_modelo_source_ids` carries both the current id and edit-lineage predecessor ids, so finalized references to pre-edit ids still block successor removal/reset. The prior S1822-002 reset cascade is also fixed in implementation: reset computes the same purchase-evidence and attachment closure as physical removal, detaches `purchase_invoice_evidence` links, emits the per-object detach/removal events plus `ledger.catalogue.reset`, and persists the transaction catalogue, invoice catalogue, and bucket event catalogue through one secure-object batch write. `config_reset` and `setup_reset` no longer delete readable ledger data through DATA reset.

The residual gap is coverage rather than behavior: `src/aeat/application/ledger/test_actions.py` directly tests finalized-reference refusal for remove, update, lifecycle transitions, and prior edit ids, and it tests successful reset cascade, but it does not directly test that `reset_ledger_catalogue` refuses when any current or edit-lineage transaction id is cited by a verified/filed revision. Add a non-tautological reset refusal test that seeds a finalized modelo revision, calls reset, and asserts no transaction, invoice-link, or event mutation occurred.
