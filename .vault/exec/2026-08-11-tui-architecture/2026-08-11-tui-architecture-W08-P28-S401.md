---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:712695c6ec2eca735c92f06942187cba88a3b367791adde7e05a948802eb4b43'
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
- `verify:` `uv run ruff check` and `uv run ruff format --check` on owned paths -> `pass`
- `verify:` `uv run ty check src/cadrumo/application/user_profile/workbench_bootstrap.py src/cadrumo/entrypoints/tui/bootstrap.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/application/user_profile/workbench_bootstrap.py src/cadrumo/entrypoints/tui/bootstrap.py` -> `pass`
- `verify:` targeted `dev.audit.duplication.run_duplication_scan` on both owned production files -> `pass`

## Notes

The broader launcher-entry test subset is blocked by concurrent unowned `launcher.py` work that now calls test providers with an operation-runtime argument although those fixtures accept none. The S401-focused suite passes.
