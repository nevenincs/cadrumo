---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S16'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W02.P04.S16 Restore Application Action

Scope: verify the restore application action and finalized-modelo guard.

## Description

- Verified `restore_manual_transaction` exists in `src/aeat/application/ledger/_actions_lifecycle.py`.
- Verified the action records the supplied reason in lifecycle history.
- Verified the finalized-modelo guard refuses restore for protected rows.

## Outcome

S16 is closed. Restore mirrors the forward lifecycle actions through the application service.

## Checks

- `pytest src/aeat/application/ledger/tests/test_actions_lifecycle.py -m "unit or integration" -q --basetemp Y:/tmp/pytest-w02-restore-lineage`

