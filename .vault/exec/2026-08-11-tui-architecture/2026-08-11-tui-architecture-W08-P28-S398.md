---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:dffd63eeeee40da5101c625469cee47516a5a05a424855b950e9b6240cee0e74'
step_id: 'S398'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Connect cadrumo.application.search to the installed workbench by assembling one immutable redacted document snapshot from the current Ledger, Declarations, filing-history, reconciliation, notification, and Modelo projections, injecting its service into the root host, and rebuilding it after authoritative child returns without implicit I/O

## Scope

- `src/cadrumo/application/search/`
- `src/cadrumo/entrypoints/tui/launcher.py`
- `and focused installed-search tests`

## Changes

- `A` `src/cadrumo/application/search/installed_workbench.py`
- `A` `src/cadrumo/application/search/tests/test_installed_workbench.py`
- `M` `src/cadrumo/entrypoints/tui/__main__.py`
- `M` `src/cadrumo/entrypoints/tui/app.py`
- `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_app.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p28-s398-review-audit.md`
- `verify:` `uv run pytest -n0 src/cadrumo/application/search/tests/test_installed_workbench.py src/cadrumo/application/search/tests/test_workbench.py src/cadrumo/entrypoints/tui/tests/test_app.py src/cadrumo/entrypoints/tui/tests/test_search.py src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py src/cadrumo/entrypoints/tui/tests/test_launcher_composition_root.py -q` -> `pass`

## Notes

- The existing installed root has no truthful owner for all six required public projections. S398 requires a coherent injected provider and refuses visibly without one; S384 must supply that provider from already-public session dependencies.
