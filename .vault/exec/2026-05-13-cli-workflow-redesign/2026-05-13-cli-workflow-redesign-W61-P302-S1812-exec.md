---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P302.S1812'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
---

# `cli-workflow-redesign` `W61.P302.S1812`

Closed plan rows:

- `W61.P302.S1812`

## Description

Captured evidence provenance actor and edit lineage for manual ledger transactions.

`TransactionEvidenceProvenanceEntry` records evidence id, evidence kind, actor, source command, link timestamp, and the bucket event id that created the evidence link.

`TransactionEditLineageEntry` records the previous transaction id, actor, source command, edit timestamp, and the bucket event id for the correction event.

`Transaction` now carries `created_by`, `source_command`, `created_event_id`, `evidence_provenance`, and `edit_lineage` as durable bucket-scoped catalogue facts. Manual transaction creation builds the bucket event before final transaction persistence so the transaction can store the create event id and the evidence provenance can point at the same event. Manual transaction updates build the update event before replacement persistence, append one edit lineage entry, and still reject provenance-only no-op corrections.

Attachment manifests now persist `captured_by` and `source_command` so evidence stored under the secure bucket has actor/source metadata aligned with ledger transaction provenance.

No archive/delete lineage and no CLI command surface were introduced in this step.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `src/aeat/application/ledger/_actions.py`
- `src/aeat/application/ledger/test_actions.py`
- `src/aeat/domain/attachments/_models.py`
- `src/aeat/domain/attachments/test_repository.py`
- `src/aeat/domain/transactions/__init__.py`
- `src/aeat/domain/transactions/_models.py`
- `src/aeat/domain/transactions/test_models.py`

## Tests

- `uv run --no-sync pytest src/aeat/domain/transactions/test_models.py src/aeat/application/ledger/test_actions.py src/aeat/domain/attachments/test_repository.py -q`
