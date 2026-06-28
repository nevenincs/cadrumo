---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S31'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W04.P08.S31 Resume CLI Tests

Scope: cover natural-key resume, exact-id resume, and ambiguity refusal with real CLI tests.

## Description

- Add CLI coverage for `work resume --modelo 130 --year 2026 --period 1T`.
- Add CLI coverage for legacy exact work-unit-id resume compatibility.
- Add CLI coverage for ambiguous visible filing targets refusing with candidate guidance and without tracebacks.
- Extend command help coverage so the natural-key resume flags remain visible.

## Outcome

Focused CLI resume tests pass and verify that the command works through real persisted workflow-run and work-unit state.

## Notes

Tests use real codebase services and repositories. No fakes, mocks, monkeypatches, skips, or xfails were introduced.
