---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W61.P302.S1807'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
---

# `cli-workflow-redesign` `W61.P302.S1807`

Closed plan rows:

- `W61.P302.S1807`

## Description

Defined strict backend contracts for manual ledger transaction workflows under `aeat.application.ledger`.

`ManualLedgerTransactionCommand` captures the bucket id, movement fields, tax classification fields, proportionality references, evidence references, actor/source command, and idempotency key for one manual ledger mutation. It normalizes operator text, currency, evidence ids, and attachment ids, and enforces the mixed-use `business_pct` coupling before any CLI command is allowed to expose manual entry.

`ManualLedgerTransactionResult` returns a bucket-qualified transaction ref, the strict transaction payload, and bucket event ids. This result shape gives the next implementation step a typed return contract for persisted manual ledger mutations.

No CLI command was added in this step.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `src/aeat/application/ledger/__init__.py`
- `src/aeat/application/ledger/_models.py`
- `src/aeat/application/ledger/test_models.py`

## Tests

- `uv run pytest src/aeat/application/ledger/test_models.py src/aeat/domain/transactions/test_repository.py -q`
