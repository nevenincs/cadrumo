---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S47'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W04.P09.S47 M036 Read-Back Tests

Scope: verify real-behavior tests for recording and reading M036 declarations.

## Description

- Ran tests that record M036 declarations and read them back through list/view.
- Verified the tests include anti-tautology coverage for unrecorded records.

## Outcome

S47 is closed. Real-runtime M036 read-back tests pass.

## Notes

- Checks run: `pytest src/aeat/application/modelo/tests/test_m036_lifecycle_read_back.py src/aeat/entrypoints/cli/tests/test_m036_command_shape.py`.
