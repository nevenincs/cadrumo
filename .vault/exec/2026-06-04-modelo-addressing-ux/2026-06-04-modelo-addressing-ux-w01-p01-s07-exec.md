---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S07'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W01.P01.S07 selector resolution coverage

Scope:
- `src/aeat/application/modelo/test_selectors.py`

## Description

- Add real storage-backed tests for active bucket resolution, explicit bucket resolution, absent visible targets, discarded exclusion, single active resolution, explicit-ID contradictions, registry revision conflicts, and visible-target ambiguity.
- Seed ambiguity through the real catalogue repository to represent legacy/historical conflicting active work.

## Outcome

Focused selector tests prove the W01.P01 resolution contract without fakes, mocks, monkeypatches, skips, or mirrored business logic.

## Notes

- `uv run pytest src/aeat/application/modelo/test_selectors.py -q` passed with 8 tests.
