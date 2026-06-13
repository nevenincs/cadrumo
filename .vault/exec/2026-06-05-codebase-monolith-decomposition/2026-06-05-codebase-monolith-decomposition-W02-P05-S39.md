---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S39'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S39 - extract live expedientes command group

Scope: `src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_*.py`.

## Description

- Add `_app_live_expedientes_cli.py` as the focused registrar module for live expedientes commands.
- Move expedientes capture, capture-all, list, view, latest, and output helpers out of `_app_live.py`.
- Register the extracted subgroup with injected active-bucket and auth-preflight callables.
- Keep `expedientes_app` exported through `_app_live.py` for consumer-facing façade compatibility.

## Outcome

The live expedientes command surface is extracted without changing operator command paths. `_app_live.py` now delegates expedientes mounting to a focused registrar and dropped from 1580 to 1177 lines, below the 1250-line objective.

## Notes

Lint and compile checks passed for `_app_live.py` and `_app_live_expedientes_cli.py`. Live capture behavior remains delegated to application live services.
