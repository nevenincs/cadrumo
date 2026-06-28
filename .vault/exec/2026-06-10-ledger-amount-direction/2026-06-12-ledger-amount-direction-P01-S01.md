---
tags: ['#exec', '#ledger-amount-direction']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S01'
related:
  - '[[2026-06-10-ledger-amount-direction-plan]]'
---

# Raw Transaction Amount Gate

## Scope

Step `P01.S01`.

## Description

- Added the non-negative magnitude validator on `RawTransaction.amount`.
- Rewrote the field documentation around magnitude plus authoritative direction.

## Outcome

`RawTransaction` rejects negative amounts on model validation, so import and manual rows share the same boundary gate.

## Notes

No sibling ledger-plan files were edited.
