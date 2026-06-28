---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W61.P302.S1811'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
---

# `cli-workflow-redesign` `W61.P302.S1811`

Closed plan rows:

- `W61.P302.S1811`

## Description

Separated durable ledger mutations from workflow review annotations.

`LedgerReviewRecord` is now a workflow attention annotation only. It stores `transaction_id`, workflow history, and `updated_at`. Its model docstring states that classification, category, business percentage, tax fields, evidence references, skip/final-disposition state, and corrections live on the bucket-scoped transaction catalogue.

`update_ledger_review` remains exported for workflow attention history, but rejects durable ledger fields, skip state, and allocation/split data with `ReviewError`.

The legacy `app ledger edit` workflow-overlay path no longer writes review-state ledger facts. It refuses mutation-like input and states that ledger review annotations cannot store ledger mutations. CLI review status is derived from `Transaction.business_classification`, not workflow review overlays.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `src/aeat/application/review/__init__.py`
- `src/aeat/application/review/_actions.py`
- `src/aeat/application/review/_models.py`
- `src/aeat/application/review/test_actions.py`
- `src/aeat/entrypoints/cli/_ledger.py`
- `src/aeat/entrypoints/cli/test_cli_surface.py`

## Tests

- `uv run --no-sync pytest src/aeat/application/review/test_actions.py src/aeat/application/review/test_models.py src/aeat/application/review/test_adapters.py src/aeat/application/review/test_edit.py src/aeat/entrypoints/cli/test_cli_surface.py -q`
