---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S105'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S105 - extract ledger read commands

Scope: `src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_read_cli.py`.

## Description

- Move ledger read/discovery/reporting commands into `_ledger_read_cli.py`.
- Keep mutating transaction update/link/allocation flows in `_ledger.py`.
- Register the read command group through `register_read_commands(app, resolve_transaction_id=_resolve_id)`.
- Preserve public command paths for providers, categories, check, preflight, history, export, list, view, status, track, and review.

## Outcome

The ledger root no longer owns the large read/reporting command block. The extracted registrar owns read-only operator surfaces and delegates transaction-id prefix resolution back to the root helper.

## Notes

The slice intentionally excludes `allocate` and `link`, which share mutation and invoice/evidence update paths.
