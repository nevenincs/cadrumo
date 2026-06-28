---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S28'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W02.P05.S28 Content-Address Authority Preserved

Scope: verify lineage resolution does not freeze transaction ids across edits.

## Description

- Verified tests assert an id-affecting edit re-derives the content-addressed transaction id.
- Verified the old id is absent from live catalogue keys and survives only as an edit-lineage back-pointer.

## Outcome

S28 is closed. Storage and audit keep content-addressed ids authoritative; lineage resolution is read-side only.

## Checks

- `pytest src/aeat/entrypoints/cli/tests/test_ledger_lineage_handle.py -m "unit or integration" -q --basetemp Y:/tmp/pytest-w02-restore-lineage`

