---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W61.P302.S1810'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
---

# `cli-workflow-redesign` `W61.P302.S1810`

Closed plan rows:

- `W61.P302.S1810`

## Description

Implemented backend policy validation for manual ledger transaction direction, zero-value evidence, `INTERNAL_TRANSFER` rows, and correction semantics.

`ManualLedgerTransactionCommand` now rejects zero-amount rows and directs zero-value evidence to existing rows. Direction sign policy is enforced at the backend boundary: `OUTGOING` rows require a negative amount, and `INCOMING` rows require a positive amount.

`INTERNAL_TRANSFER` is allowed only as a non-tax-relevant manual ledger transaction. It must not carry category, IVA fields, IRPF category, usage ratio, prorrata reference, purchase invoice evidence, or attachments.

Update semantics now treat replacement as correction. Update events include `mutation_kind=correction` and `previous_transaction_id`. Corrections must change at least one ledger field; provenance-only and no-op updates are rejected through the mutation signature.

`TransactionValidationError` is exported from the public transaction package surface for backend callers and tests.

No CLI command was added in this step.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `src/aeat/application/ledger/_actions.py`
- `src/aeat/application/ledger/_models.py`
- `src/aeat/application/ledger/test_actions.py`
- `src/aeat/application/ledger/test_models.py`
- `src/aeat/domain/transactions/__init__.py`

## Tests

- `uv run --no-sync pytest src/aeat/application/ledger/test_models.py src/aeat/application/ledger/test_actions.py src/aeat/domain/transactions/test_models.py src/aeat/domain/transactions/test_repository.py -q`
