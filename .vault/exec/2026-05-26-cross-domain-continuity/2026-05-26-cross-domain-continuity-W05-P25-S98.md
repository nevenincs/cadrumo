---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S98'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# regression tests for bulk and rule paths

## Scope

- `src/aeat/entrypoints/cli/test_ledger_bulk_classify.py`

## Description

- Reconciled the bulk and rule classification regression coverage to the grouped P25 execution evidence.
- Confirmed `6c4ec924c` supplied the reviewed implementation.
- Added this per-step execution record without changing production sources.

## Outcome

The historical evidence supports the checked row. This record restores the one-Step, one-record traceability edge.

## Notes

The same grouped evidence also supports S97; each row receives its own record.
