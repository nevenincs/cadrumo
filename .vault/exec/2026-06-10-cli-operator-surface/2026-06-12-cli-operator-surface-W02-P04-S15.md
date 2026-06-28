---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S15'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W02.P04.S15 Ledger Restore Transition

Scope: verify the public restore-to-ACTIVE lifecycle transition.

## Description

- Verified `restore_manual_transaction` moves STASHED and ARCHIVED rows back to ACTIVE.
- Verified SPLIT and MERGED lineage remain outside this restore transition.

## Outcome

S15 is closed. Restore uses the application lifecycle service, not CLI business logic.

## Checks

- `pytest src/aeat/application/ledger/tests/test_actions_lifecycle.py src/aeat/entrypoints/cli/tests/test_ledger_restore_journey.py src/aeat/entrypoints/cli/tests/test_ledger_lineage_handle.py -m "unit or integration" -q --basetemp Y:/tmp/pytest-w02-restore-lineage`

