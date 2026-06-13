---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S24'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S24 - residual ledger ratios extraction

Scope: `src/aeat/entrypoints/cli/_ledger.py` and `src/aeat/entrypoints/cli/_ledger_ratios_cli.py`.

## Description

- Added focused `_ledger_ratios_cli` command module for `app ledger ratios`.
- Moved `list`, `set`, `unset`, `eligible`, and `validate` ratio commands plus ratio-specific helpers out of `_ledger.py`.
- Preserved `ratios_app` as a top-level `_ledger` façade export for existing tests and consumers.
- Mounted the ratios app through `register_ratios_commands(app)`.

## Outcome

Extraction completed. The ledger root now delegates ratio command registration to `_ledger_ratios_cli` and no longer defines ratio command bodies inline.

## Notes

The extracted module still delegates persistence and validation behavior to `application.ledger`, `application.user_profile`, and domain repositories; no new business logic was added to the CLI.
