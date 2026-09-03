---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:36a160385e507c587ae137e319601dd3fefe9d488c568c7f468b19065345ce9e'
step_id: 'S404'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Compose the production Modelo workspace factory from admitted declaration targets, canonical workspace sessions, and existing Modelo editor pages

## Scope

- `src/cadrumo/entrypoints/tui/modelo/`
- `src/cadrumo/entrypoints/tui/launcher.py`
- `and focused installed Modelo navigation tests`

## Changes

- `M` `src/cadrumo/application/workbench_generation.py`
- `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `M` `src/cadrumo/entrypoints/tui/installed_session.py`
- `verify:` `uv run --no-sync pytest -q -m integration src/cadrumo/entrypoints/tui/tests/test_installed_workbench.py` -> `pass`
