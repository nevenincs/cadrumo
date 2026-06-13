---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S11'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W01.P02.S11 revision selector coverage

Scope:
- `src/aeat/application/modelo/test_selectors.py`

## Description

- Add persisted calculation revision tests for current, latest-draft, latest-verified, filed, and explicit revision selectors.
- Add command-specific current draft and current verified state-gate tests.
- Assert candidate short IDs and stored revision identity rather than mirroring selector implementation.

## Outcome

Selector behavior is covered over the real calculation-revision catalogue with no fakes, mocks, monkeypatches, skips, or xfails.

## Notes

- `uv run pytest src/aeat/application/modelo/test_selectors.py ...` passed in the focused W01.P02 run.
