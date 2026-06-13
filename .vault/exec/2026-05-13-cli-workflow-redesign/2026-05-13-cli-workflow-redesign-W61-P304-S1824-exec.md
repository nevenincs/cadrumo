---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P304.S1824'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-14-cli-workflow-redesign-w61-p304-s1824-code-review-audit]]"
  - "[[2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
---

# `cli-workflow-redesign` `W61.P304.S1824`

Closed plan rows:

- `W61.P304.S1824`

## Description

Replaced stale review queue drill guidance for `ledger_transaction` rows with app-ledger-owned inspection guidance. The review adapter now emits `aeat app ledger review --id {transaction_id}` as the drill command for transaction review rows, and the existing review projection preserves that command as the queue row's `canonical_next_command` while keeping `current_owner_surface` as `app ledger`.

This keeps `aeat app review queue` and `aeat app review show` read-only. The queue no longer points ledger transaction rows at the stale `aeat app ledger edit --set ...` path, and it does not make review overlays responsible for durable transaction facts. Ledger transaction drill-down now routes to the ledger-owned row inspection surface.

The plan row names app ledger lifecycle commands. This closeout is specifically the ledger-owned `review` inspection command. It does not claim global removal of `app ledger edit --set`; remaining edit/parser infrastructure is outside this narrow review-queue drill-command replacement.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P304-S1824-code-review-audit.md`
- `src/aeat/application/review/_adapters.py`
- `src/aeat/application/review/test_adapters.py`
- `src/aeat/application/review/test_models.py`
- `src/aeat/entrypoints/cli/test_apex_workflow_verification.py`

## Tests

- `uv run --no-sync ruff check src/aeat/application/review/_adapters.py src/aeat/application/review/test_adapters.py src/aeat/application/review/test_models.py src/aeat/entrypoints/cli/test_apex_workflow_verification.py`
  - All checks passed
- `uv run --no-sync ty check src/aeat/application/review/_adapters.py src/aeat/application/review/test_adapters.py src/aeat/application/review/test_models.py src/aeat/entrypoints/cli/test_apex_workflow_verification.py`
  - All checks passed
- `uv run --no-sync pytest src/aeat/application/review/test_adapters.py src/aeat/application/review/test_models.py src/aeat/application/review/test_aggregator.py src/aeat/entrypoints/cli/test_apex_workflow_verification.py -q`
  - 38 passed

Coverage includes bucket-scoped transaction review adapter behavior, strict review item Pydantic serialization and validation, cross-source review aggregation, and the real CLI workflow path from `config init` through `app ledger import` to `app review queue --source-kind ledger_transaction`.

## Review

Formal code review reported no findings in `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P304-S1824-code-review-audit.md`.
