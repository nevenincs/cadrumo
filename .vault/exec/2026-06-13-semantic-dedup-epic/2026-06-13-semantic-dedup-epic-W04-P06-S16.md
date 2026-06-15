---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-15'
step_id: 'S16'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# Consolidate the live-CLI _metric_line and auth-preflight guard onto shared helpers in _app_live_auth_preflight and redirect rendering, expedientes, justificante, notifications

## Scope

- `src/aeat/entrypoints/cli/_app_live_auth_preflight.py`

## Description

- Keep the canonical `_metric_line` in `_app_live_auth_preflight.py`; add a shared
  `run_auth_preflight(preflight, *, family)` guard there.
- Redirect `_app_live_rendering.py` and `_app_live_expedientes_cli.py` to import
  `_metric_line`; remove their duplicate defs.
- Replace the per-module `_run_auth_preflight` guards in expedientes, justificante
  and notifications with calls to the shared `run_auth_preflight(..., family=...)`.

## Outcome

Five duplicate defs removed. 25 live-read-subgroup tests pass; ruff and
collect-only clean. Landed as commit `e59a4fb12`.

## Notes

Two failing tests in the wider run (`test_backend_boundary` skip-language meta-lint
and a `modelo reconcile` tax_id mismatch) are peer/pre-existing, outside this
surface.
