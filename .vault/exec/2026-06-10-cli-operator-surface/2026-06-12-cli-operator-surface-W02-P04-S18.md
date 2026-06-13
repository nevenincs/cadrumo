---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S18'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W02.P04.S18 Ledger Restore CLI Verb

Scope: verify the `aeat app ledger restore` CLI surface.

## Description

- Verified `ledger_restore` is registered under `app ledger restore`.
- Verified live help exposes transaction id, `--reason`, `--yes`, and `--actor`.
- Verified the CLI delegates to `restore_manual_transaction`.

## Outcome

S18 is closed. The CLI surface is a consumer of the application restore service.

## Checks

- `aeat --language en app ledger restore --help`
- `pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py src/aeat/entrypoints/cli/tests/test_self_referential_string_conformance.py dev/docs/tests/test_cli_reference_drift.py -m "unit or integration or hex_core" -q --basetemp Y:/tmp/pytest-w02-conformance`

