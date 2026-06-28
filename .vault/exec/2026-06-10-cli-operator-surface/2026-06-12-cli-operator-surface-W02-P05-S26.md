---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S26'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W02.P05.S26 View Lineage Handle

Scope: verify `ledger view` resolves superseded edit-lineage ids.

## Description

- Verified `ledger view OLD-ID` resolves to the current corrected row after edit.
- Verified unknown ids with no lineage still refuse.

## Outcome

S26 is closed. View accepts old edit-lineage handles only where a current row owns the lineage.

## Checks

- `pytest src/aeat/entrypoints/cli/tests/test_ledger_lineage_handle.py -m "unit or integration" -q --basetemp Y:/tmp/pytest-w02-restore-lineage`

