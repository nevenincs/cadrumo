---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S38'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# `codebase-monolith-decomposition` `W02.P05.S38`

## Scope

Live root closure selection.

## Description

- Measured `_app_live.py` at 1580 lines before the slice.
- Ran exact discovery over live root commands and existing live registrar modules.
- Ran semantic RAG search for live CLI root closure candidates.
- Selected the `portals` subgroup because it is a local read-only catalogue surface with isolated formatting helpers.

## Outcome

The selected closure group was `aeat app live portals`, targeting extraction into `_app_live_portals_cli.py`.

## Notes

No data loss. Work was performed in a dirty shared workspace; unrelated concurrent edits were left intact.
