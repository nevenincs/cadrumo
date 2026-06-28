---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S49'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W04.P09.S49 M036 Locale And Reference Gates

Scope: verify M036 list/view locale strings and generated reference state.

## Description

- Verified live help for `aeat app modelo m036 list`.
- Ran CLI-reference drift after the M036 command surface was present.
- Ran documented-command conformance.

## Outcome

S49 is closed. M036 list/view help and generated CLI reference are synchronized.

## Notes

- Checks run: `pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py dev/docs/tests/test_cli_reference_drift.py`.
