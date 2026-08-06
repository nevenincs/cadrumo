---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:c34e72703c469e171ca0f6a7b4cfa9955aafb572baf3bd06544f7ca1eb7e2d4a'
step_id: 'S17'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W02.P04.S17 Restore Audit Event

Scope: verify restore has its own audit event type.

## Description

- Verified restore emits `BucketEventType.LEDGER_TRANSACTION_RESTORED`.
- Verified tests assert restore event ids and lifecycle-lineage event references.

## Outcome

S17 is closed. Restore is auditable as a distinct inverse lifecycle event.

## Checks

- `pytest src/aeat/application/ledger/tests/test_actions_lifecycle.py src/aeat/entrypoints/cli/tests/test_ledger_restore_journey.py -m "unit or integration" -q --basetemp Y:/tmp/pytest-w02-restore-lineage`
