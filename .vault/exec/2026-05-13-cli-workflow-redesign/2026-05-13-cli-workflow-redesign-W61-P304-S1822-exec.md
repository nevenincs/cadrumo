---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P304.S1822'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-14-cli-workflow-redesign-w61-p304-s1822-code-review-audit]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-ledger-transaction-removal-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]"
---

# `cli-workflow-redesign` `W61.P304.S1822`

Closed plan rows:

- `W61.P304.S1822`

## Description

Implemented bucket-local ledger removal and reset protections in the backend. Ledger removal, manual transaction update, archive/stash lifecycle transitions, and ledger catalogue reset now check finalized modelo references before mutating ledger data.

Finalized blockers are calculation revisions in `VERIFIED_COMPLETE`, `FILED`, or `FILED_SUPERSEDED` state whose `source_transaction_ids` intersect the candidate ledger transaction ids. The guard closure includes the current transaction id plus prior edit-lineage ids, so a content-derived transaction id cannot be changed by edit and then physically removed through a successor id. Ledger catalogue reset applies the same closure to every transaction in the catalogue.

Calculation revisions now persist `source_transaction_ids` for bucket-derived calculations, and calculation revision identity includes those ids. Bucket aggregation collects source transaction ids from IVA observations, prorrata references, and Renta expense observations, then passes them into modelo calculation.

Ledger reset now applies dependency cleanup instead of only clearing the transaction catalogue. It detaches bucket-local `purchase_invoice_evidence` links, emits per-object cascade events, emits `ledger.catalogue.reset`, clears the transaction catalogue, and saves transaction catalogue, invoice catalogue, and bucket-event catalogue through one secure-object batch.

`config_reset.DATA` and `setup_reset.DATA` documentation now state that those flows quarantine undecryptable secure-object rows only. Readable ledger data reset is owned by the ledger backend so finalized modelo protections run before removal.

The S1822 audit initially found two material issues: a CRITICAL finalized-modelo guard bypass through mutable transaction ids and a HIGH reset cascade gap. Both were fixed. Re-review found no remaining HIGH or CRITICAL findings. The remaining LOW reset-refusal coverage gap was closed with a direct finalized-reference reset regression test.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P304-S1822-code-review-audit.md`
- `src/aeat/domain/modelos/_calculation_revision.py`
- `src/aeat/application/aggregation/_modelo_bindings.py`
- `src/aeat/application/modelo/_actions.py`
- `src/aeat/application/modelo/test_bucket_aggregation_flow.py`
- `src/aeat/domain/invoices/_repository.py`
- `src/aeat/application/ledger/_models.py`
- `src/aeat/application/ledger/_actions.py`
- `src/aeat/application/ledger/__init__.py`
- `src/aeat/application/ledger/test_actions.py`
- `src/aeat/application/config_reset.py`
- `src/aeat/application/setup_reset.py`

## Tests

- `uv run --no-sync ruff check src/aeat/domain/modelos/_calculation_revision.py src/aeat/application/aggregation/_modelo_bindings.py src/aeat/application/modelo/_actions.py src/aeat/domain/invoices/_repository.py src/aeat/application/ledger/_models.py src/aeat/application/ledger/_actions.py src/aeat/application/ledger/__init__.py src/aeat/application/ledger/test_actions.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/config_reset.py src/aeat/application/setup_reset.py`
  - All checks passed
- `uv run --no-sync ty check src/aeat/domain/modelos/_calculation_revision.py src/aeat/application/aggregation/_modelo_bindings.py src/aeat/application/modelo/_actions.py src/aeat/domain/invoices/_repository.py src/aeat/application/ledger/_models.py src/aeat/application/ledger/_actions.py src/aeat/application/ledger/__init__.py src/aeat/application/ledger/test_actions.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/config_reset.py src/aeat/application/setup_reset.py`
  - All checks passed
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/domain/modelos/test_repository_sensitivity_class.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/application/test_config_reset.py src/aeat/application/test_setup_reset.py -q`
  - 77 passed
- `uv run --no-sync pytest src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/application/modelo/test_import_flow.py -q`
  - 37 passed

Coverage includes persisted calculation source ids, source-id participation in calculation revision identity, finalized-reference refusal for remove/update/lifecycle/reset, prior-edit-id removal refusal, reset dependency cascade, purchase evidence detachment, per-object removal events, secure-object batch persistence, and config/setup reset scope wording.
