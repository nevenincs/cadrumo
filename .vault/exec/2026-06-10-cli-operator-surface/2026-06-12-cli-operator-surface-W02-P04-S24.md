---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S24'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W02.P04.S24 Restore CLI Reference Gate

Scope: verify documented command conformance and CLI reference drift after restore.

## Description

- Ran documented-command conformance, D5 self-referential-string conformance, and CLI-reference drift tests.
- The generated CLI reference is in sync with the restore command tree.

## Outcome

S24 is closed. Restore introduces no documented-command or reference drift.

## Checks

- `pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py src/aeat/entrypoints/cli/tests/test_self_referential_string_conformance.py dev/docs/tests/test_cli_reference_drift.py -m "unit or integration or hex_core" -q --basetemp Y:/tmp/pytest-w02-conformance`

