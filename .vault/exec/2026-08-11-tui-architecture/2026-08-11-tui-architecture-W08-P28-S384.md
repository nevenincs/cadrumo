---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:4ab44a3ba9461be674c84a54e63e44e559f49fcd9e1757aaca657b34a54211a8'
step_id: 'S384'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Compose secure profile, overview, Ledger, declaration, evidence, notification, operation, and destination factories for one installed session

## Scope

- `src/cadrumo/entrypoints/tui/launcher.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/__main__.py`
- `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p28-s384-review-audit.md`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `A` `.vault/exec/2026-08-11-tui-architecture/2026-08-11-tui-architecture-W08-P28-S384.md`
- `verify:` `uv run --no-sync pytest -n0 -q src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py src/cadrumo/entrypoints/tui/tests/test_launcher_composition_root.py src/cadrumo/entrypoints/tui/tests/test_app.py src/cadrumo/entrypoints/tui/tests/test_navigation.py src/cadrumo/entrypoints/tui/tests/test_search.py src/cadrumo/entrypoints/tui/tests/test_account.py src/cadrumo/entrypoints/tui/ledger/tests src/cadrumo/entrypoints/tui/declarations/tests src/cadrumo/entrypoints/tui/aeat_sync/tests src/cadrumo/application/search/tests/test_installed_workbench.py src/cadrumo/application/aeat_sync/tests/test_workspace.py src/cadrumo/application/ledger/tests/test_workspace.py src/cadrumo/application/modelo/tests/test_declarations_workspace.py src/cadrumo/application/modelo/tests/test_declarations_calendar.py` -> `pass`
- `verify:` `uv run --no-sync ruff format --check src/cadrumo/entrypoints/tui/launcher.py src/cadrumo/entrypoints/tui/__main__.py src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/tui/launcher.py src/cadrumo/entrypoints/tui/__main__.py src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/entrypoints/tui/launcher.py src/cadrumo/entrypoints/tui/__main__.py src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py` -> `pass`
- `verify:` `uv run --no-sync basedpyright src/cadrumo/entrypoints/tui/launcher.py src/cadrumo/entrypoints/tui/__main__.py src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py` -> `pass`
- `verify:` `npx --yes jscpd@4.2.0 src/cadrumo/entrypoints/tui/launcher.py src/cadrumo/entrypoints/tui/__main__.py src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py --format python --min-lines 6 --min-tokens 80 --max-size 250kb --reporters console --noTips` -> `pass`
