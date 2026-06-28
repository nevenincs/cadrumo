---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S27'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W02.P05.S27 Track Lineage Handle

Scope: verify `ledger track` resolves superseded edit-lineage ids.

## Description

- Verified `ledger track OLD-ID` resolves to the corrected current row.
- Verified the track payload includes the edit-lineage projection.

## Outcome

S27 is closed. Track follows old edit-lineage handles at the read boundary.

## Checks

- `pytest src/aeat/entrypoints/cli/tests/test_ledger_lineage_handle.py -m "unit or integration" -q --basetemp Y:/tmp/pytest-w02-restore-lineage`

