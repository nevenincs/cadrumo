---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S10'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W01.P02.S10 filed pointer invariants

Scope:
- `src/aeat/application/modelo/_revision_persistence.py`

## Description

- Preserve the existing filing persistence invariant that filing advances `filed_calculation_revision_id` and `current_filing_record_id`.
- Ensure the duplicate-draft pointer fix does not mutate filed pointers or current filing pointers.
- Add focused assertions around current, filed, and filing pointer state after duplicate calculate and file flows.

## Outcome

Filed answer pointers remain separate from current calculation selection while the duplicate-draft current pointer gap is closed.

## Notes

- Covered by focused file-flow tests.
