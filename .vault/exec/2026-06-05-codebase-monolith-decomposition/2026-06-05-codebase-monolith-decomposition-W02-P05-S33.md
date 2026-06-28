---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S33'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# `codebase-monolith-decomposition` `W02.P05.S33`

## Scope

Ledger rule registrar extraction.

## Description

- Reconciled the existing `_ledger_rules_cli.py` registrar with `_ledger.py`.
- Imported `register_rule_commands` into `_ledger.py`.
- Removed the duplicated rule sub-app block from `_ledger.py`.
- Mounted `register_rule_commands(app)` after the other ledger sub-app registrars.

## Outcome

`_ledger.py` no longer owns the ledger rule command implementations. Rule commands remain registered under the existing `aeat app ledger rule` path through `_ledger_rules_cli.py`.

## Notes

No data loss. Work was performed in a dirty shared workspace; unrelated concurrent edits were left intact.
