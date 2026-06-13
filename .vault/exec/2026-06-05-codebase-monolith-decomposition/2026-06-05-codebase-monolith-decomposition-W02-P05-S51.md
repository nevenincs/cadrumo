---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S51'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S51 - extract residual config auth command group

Scope: `src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/*.py`.

## Description

- Move the `aeat config auth` Typer app and command bodies into `_config/_auth.py`.
- Keep `_config/__init__.py` as the config facade that imports and mounts `auth_app`.
- Preserve provider choices, output-language activation, backend auth service calls, and existing output envelopes.
- Export `auth_app` from the config facade for existing consumers.

## Outcome

The config auth command surface now lives in a focused module. `_config/__init__.py` no longer owns auth command bodies and remains the composition surface for the config command tree.

## Notes

No command path changed; `aeat config auth providers|configure|status|test|login|clear` continue to mount under the same subgroup.
