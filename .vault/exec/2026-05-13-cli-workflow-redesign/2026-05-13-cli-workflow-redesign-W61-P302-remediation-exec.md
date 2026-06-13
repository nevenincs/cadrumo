---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P302.remediation'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
---

# `cli-workflow-redesign` `W61.P302.remediation`

Closed audit rows:

- `W61.P302-001`
- `W61.P302-002`
- `W61.P302-003`
- `W61.P302-004`
- `W61.P302-005`
- `W61.P302-T001`

## Description

Closed the W61.P302 remediation findings for manual ledger transaction persistence.

Manual ledger commands now use singular `purchase_invoice_evidence_id` and reject multi purchase evidence, duplicate attachments, zero rows, invalid direction signs, and internal-transfer tax or evidence payloads.

Ledger services resolve a bucket-scoped transaction catalogue repository, reject repository bucket mismatches, verify evidence before persistence, append the bucket event, and then save the transaction catalogue. Purchase evidence requires an existing received invoice in the command bucket. Attachment evidence requires a manifest, blob verification, matching bucket ownership, and compatible linked transaction state.

Transactions now store tax fields, `purchase_invoice_evidence_id`, `attachment_ids`, `created_by`, `source_command`, `created_event_id`, `evidence_provenance`, and `edit_lineage` as durable catalogue facts. Updates preserve original creation provenance and append correction lineage with `mutation_kind=correction`. Review annotations no longer store durable ledger facts.

Residual risk remains for `W61.P302-R006`: event and catalogue writes are separate. Current ordering prevents a durable transaction without an event, but inverse event-only drift can still occur.

## Modified Paths

- `src/aeat/application/ledger/_actions.py`
- `src/aeat/application/ledger/test_actions.py`
- `src/aeat/application/ledger/test_models.py`
- `src/aeat/domain/attachments/_models.py`
- `src/aeat/domain/attachments/_repository.py`
- `src/aeat/domain/attachments/test_repository.py`
- `src/aeat/domain/invoices/_models.py`
- `src/aeat/domain/transactions/_models.py`
- `src/aeat/domain/transactions/test_models.py`

## Tests

- `uv run --no-sync pytest src/aeat/application/ledger/test_models.py src/aeat/application/ledger/test_actions.py src/aeat/domain/transactions/test_models.py src/aeat/domain/transactions/test_repository.py src/aeat/domain/attachments/test_repository.py src/aeat/domain/invoices/test_models.py -q`
  - 58 passed
- `uv run --no-sync ty check src/aeat/application/ledger src/aeat/domain/transactions src/aeat/domain/attachments/_models.py src/aeat/domain/attachments/_repository.py src/aeat/domain/invoices/_models.py`
  - All checks passed
