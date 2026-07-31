---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:91af2b5b1546cca1c1c9e4e2692a3f0dfb8c63af34ab8bc5c47d610e15a1a7a4'
step_id: 'S25'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W02.P05.S25 History Lineage Handle

Scope: verify `ledger history` resolves superseded edit-lineage ids.

## Description

- Verified `_resolve_read_id` delegates to `resolve_lineage_transaction_id`.
- Verified `ledger history OLD-ID` resolves to the current row and surfaces the lineage chain after edit.

## Outcome

S25 is closed. History accepts old edit-lineage handles at the operator read boundary.

## Checks

- `pytest src/aeat/entrypoints/cli/tests/test_ledger_lineage_handle.py -m "unit or integration" -q --basetemp Y:/tmp/pytest-w02-restore-lineage`
