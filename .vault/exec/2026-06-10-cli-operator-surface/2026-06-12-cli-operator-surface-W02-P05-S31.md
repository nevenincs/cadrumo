---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S31'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W02.P05.S31 Lineage Conformance Gates

Scope: verify documented-command and D5 gates after lineage read-boundary changes.

## Description

- Ran documented-command conformance, D5 self-referential-string conformance, and CLI-reference drift tests.
- Confirmed lineage read surfaces introduce no hint drift.

## Outcome

S31 is closed. W02 lineage is compatible with the operator-surface conformance gates.

## Checks

- `pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py src/aeat/entrypoints/cli/tests/test_self_referential_string_conformance.py dev/docs/tests/test_cli_reference_drift.py -m "unit or integration or hex_core" -q --basetemp Y:/tmp/pytest-w02-conformance`

