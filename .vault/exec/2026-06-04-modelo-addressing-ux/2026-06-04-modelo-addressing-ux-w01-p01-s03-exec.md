---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S03'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W01.P01.S03 visible-target-first work-unit lookup

Scope:
- `src/aeat/application/modelo/_selectors.py`

## Description

- Add `visible_target_work_units`.
- Search non-discarded work units by bucket, modelo, filing year, and period before considering registry-revision exact targets.
- Return an absent resolution when no visible-target work unit exists.

## Outcome

The selector now preserves the ADR rule that operator-visible filing targets are resolved before exact registry-revision identity can create or select work.

## Notes

- Tests cover absent targets and discarded work-unit exclusion.
