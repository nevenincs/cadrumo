---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S21'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S21 - residual config apoderado extraction

Scope: `src/aeat/entrypoints/cli/_config/__init__.py` and `src/aeat/entrypoints/cli/_config/_apoderado.py`.

## Description

- Added focused `_config._apoderado` command module for the auth apoderado subtree.
- Moved `scopes list`, `status`, `configure`, `clear`, and `check` command functions out of the config root.
- Registered apoderado through a registrar that receives the active-profile pointer resolver from the config façade.
- Preserved `apoderado_app` as a top-level config façade export for consumers.
- Made registrar mounting per receiving `auth_app` so duplicate `__init__` imports used by legacy tests still mount the subtree.

## Outcome

Extraction completed. The config root now delegates apoderado command registration to `_config._apoderado` and no longer defines the apoderado command bodies inline.

## Notes

The extracted module still delegates auth behavior to `application.auth`; no new business logic was added to the CLI.
