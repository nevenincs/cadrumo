---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:99d87688d760c55f15abf2f035995d79499ae714b332032fd3ae73b310d011d8'
step_id: 'S401'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Build a child-process session bootstrap coordinator for recognized profile inventory, resumable custody, login, cancellation, degraded inventory, and zero-profile registration without importing dev fixtures or the CLI

## Scope

- `src/cadrumo/application/user_profile/workbench_bootstrap.py`
- `src/cadrumo/entrypoints/tui/bootstrap.py`
- `and focused bootstrap tests`

## Changes

- `M` `src/cadrumo/application/user_profile/workbench_bootstrap.py`
- `M` `src/cadrumo/application/user_profile/tests/test_workbench_bootstrap.py`
- `M` `src/cadrumo/entrypoints/tui/bootstrap.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_bootstrap.py`
- `M` `.vault/audit/2026-09-03-tui-architecture-w08-p28-s401-review-audit.md`
- `verify:` `uv run pytest -q src/cadrumo/application/user_profile/tests/test_workbench_bootstrap.py src/cadrumo/entrypoints/tui/tests/test_bootstrap.py` -> `pass`
- `verify:` `uv run pytest -q src/cadrumo/application/user_profile/tests/test_workbench_bootstrap.py src/cadrumo/entrypoints/tui/tests/test_bootstrap.py src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py src/cadrumo/entrypoints/tui/tests/test_launcher_composition_root.py` -> `pass`
- `verify:` `uv run ruff check` and `uv run ruff format --check` on owned paths -> `pass`
- `verify:` `uv run ty check src/cadrumo/application/user_profile/workbench_bootstrap.py src/cadrumo/entrypoints/tui/bootstrap.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/application/user_profile/workbench_bootstrap.py src/cadrumo/entrypoints/tui/bootstrap.py` -> `pass`
- `verify:` targeted `dev.audit.duplication.run_duplication_scan` on both owned production files -> `pass`
