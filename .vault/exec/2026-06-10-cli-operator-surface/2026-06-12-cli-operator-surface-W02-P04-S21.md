---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S21'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W02.P04.S21 Restore Locale Strings

Scope: verify restore help and event locale strings.

## Description

- Verified `cli.ledger.restore.*` locale strings exist for help, id, reason, confirmation, and actor prompts.
- Verified live English help renders the restore command from the locale catalogue.

## Outcome

S21 is closed. Restore help is represented in the locale surface.

## Checks

- `aeat --language en app ledger restore --help`
- `pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py src/aeat/entrypoints/cli/tests/test_self_referential_string_conformance.py dev/docs/tests/test_cli_reference_drift.py -m "unit or integration or hex_core" -q --basetemp Y:/tmp/pytest-w02-conformance`

