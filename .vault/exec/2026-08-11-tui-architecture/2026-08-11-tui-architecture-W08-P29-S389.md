---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:f41bc842aef9fa2e31afc0df9987a908ca924501932b7feb77f14178767db37a'
step_id: 'S389'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove the installed aeat --tui process composes the exact admitted destination catalogue and returns from every journey without a CLI-to-TUI import

## Scope

- `src/cadrumo/entrypoints/tui/tests/test_installed_workbench.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/tests/test_installed_workbench.py`
- `A` `src/cadrumo/entrypoints/tui/tests/workbench_session.py`
- `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `verify:` `uv run --no-sync pytest -q -m integration src/cadrumo/entrypoints/tui/tests/test_installed_workbench.py` -> `pass`
