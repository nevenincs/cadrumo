---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S48'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S48 - extract residual ledger root command groups

Scope: `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_*.py`.

## Description

- Move `ledger import` into a focused `_ledger_import_cli.py` registrar.
- Move provider catalogue validation and import path/result helper functions with the command.
- Move lifecycle mutation commands into `_ledger_lifecycle_cli.py`.
- Move classification-rule commands and helpers into `_ledger_rules_cli.py`.
- Wire `register_import_commands(app)` from the ledger root.
- Wire `register_lifecycle_commands(app)` and `register_rule_commands(app)` from the ledger root.
- Preserve the existing import application service, currency normalizer wiring, and output envelope.

## Outcome

`aeat app ledger import`, lifecycle mutation commands, and the `rule` subgroup are now registered from focused CLI modules. `_ledger.py` dropped to 1946 lines after this slice.

## Notes

Automatic import sorting was rerun after extraction. Command names and existing output envelopes were preserved.
