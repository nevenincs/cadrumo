---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S35'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# `codebase-monolith-decomposition` `W02.P05.S35`

## Scope

Config root closure selection.

## Description

- Measured `_config/__init__.py` at 2500 lines before the slice.
- Ran exact discovery over config root commands and existing config registrar modules.
- Ran semantic RAG search for config CLI root closure candidates.
- Selected the core `auth` command group because auth providers, configure, status, test, login, and clear already formed a coherent sub-app.

## Outcome

The selected closure group was `aeat config auth`, targeting extraction into `_config/_auth.py`.

## Notes

No data loss. Work was performed in a dirty shared workspace; unrelated concurrent edits were left intact.
