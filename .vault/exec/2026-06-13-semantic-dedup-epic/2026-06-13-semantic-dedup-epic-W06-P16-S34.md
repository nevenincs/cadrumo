---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S34'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# D1 Extract one id-truncation display helper for the four ledger-rules sites

## Scope

- `src/aeat/entrypoints/cli/_ledger_rules_cli.py`

## Description

- Added `_short_display_id` to `_ledger_rules_cli` and routed the four identical
  `{id}[:16]...` table-display idioms through it.
- `ruff format` wrapped the two comprehension lines that crossed 120 chars.

## Outcome

Committed as `78c7a6aa9`, tagged `relocation:_short_display_id`. Ruff clean;
ledger contract test green, collection clean.

## Notes

Low-severity intra-module dedup. The three codebase-wide id-truncation
algorithms (`compute_display_id_width` min-unambiguous-prefix, `short_id`
fixed `[-12:]` suffix, this fixed `[:16]` prefix-ellipsis) are constraint-
divergent and intentionally NOT merged per the Pass-3 audit.
