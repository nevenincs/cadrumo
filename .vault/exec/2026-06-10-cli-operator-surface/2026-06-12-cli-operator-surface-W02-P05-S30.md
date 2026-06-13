---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S30'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W02.P05.S30 Lineage Help And Guide Note

Scope: verify lineage help text and correct-ledger id-churn note.

## Description

- Verified read-command live help remains in sync with locale/documented command gates.
- Verified `correct-ledger-entries.md` explains that old ids still answer in `history`, `view`, and `track`, while further mutations require the current id.

## Outcome

S30 is closed. Operator docs describe the id-churn behavior without changing storage identity.

## Checks

- `aeat --language en app ledger history --help`
- `aeat --language en app ledger view --help`
- `aeat --language en app ledger track --help`
- `pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py src/aeat/entrypoints/cli/tests/test_self_referential_string_conformance.py dev/docs/tests/test_cli_reference_drift.py -m "unit or integration or hex_core" -q --basetemp Y:/tmp/pytest-w02-conformance`

