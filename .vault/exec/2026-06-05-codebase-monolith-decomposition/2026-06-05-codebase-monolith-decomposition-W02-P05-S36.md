---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S36'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# `codebase-monolith-decomposition` `W02.P05.S36`

## Scope

Config auth registrar extraction.

## Description

- Moved the core auth command bodies out of `_config/__init__.py`.
- Reused the focused `_config/_auth.py` module as the `auth_app` owner.
- Updated `_config/__init__.py` to import `auth_app` from `_config/_auth.py`.
- Preserved apoderado and diagnostics mounting on the same `auth_app` facade.

## Outcome

`_config/__init__.py` no longer owns the core auth command implementations. The public command paths under `aeat config auth` are preserved.

## Notes

No data loss. Work was performed in a dirty shared workspace; unrelated concurrent edits were left intact.
