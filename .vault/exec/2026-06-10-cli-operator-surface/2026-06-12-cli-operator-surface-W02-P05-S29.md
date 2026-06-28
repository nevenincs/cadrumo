---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S29'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W02.P05.S29 Lineage Read Tests

Scope: verify real-behavior tests for old-id history, view, and track.

## Description

- Verified tests record an id, edit the row, and assert the old id resolves through `history`, `view`, and `track`.
- Verified chained edits and unknown-id refusal are covered.

## Outcome

S29 is closed. The stable lineage handle behavior is covered by CLI real-behavior tests.

## Checks

- `pytest src/aeat/entrypoints/cli/tests/test_ledger_lineage_handle.py -m "unit or integration" -q --basetemp Y:/tmp/pytest-w02-restore-lineage`

