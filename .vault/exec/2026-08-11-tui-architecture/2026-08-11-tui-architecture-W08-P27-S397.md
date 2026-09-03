---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:d581cee35104ae790145af73d2ebdc756fd2b6074bf8451c1b0e21cbad7c2932'
step_id: 'S397'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Define a safe immutable AEAT Sync workspace projection that joins overview, census, filed-declaration, notification, evidence-comparison, and reconciliation facts while excluding protected taxpayer values and preserving source availability, freshness, contradiction, and supported-action axes

## Scope

- `src/cadrumo/application/aeat_sync/workspace.py and focused application tests`

## Changes

- `M` `src/cadrumo/application/aeat_sync/__init__.py`
- `M` `src/cadrumo/application/aeat_sync/workspace.py`
- `A` `src/cadrumo/application/aeat_sync/tests/__init__.py`
- `M` `src/cadrumo/application/aeat_sync/tests/test_workspace.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `A` `.vault/exec/2026-08-11-tui-architecture/2026-08-11-tui-architecture-W08-P27-S397.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/aeat_sync/tests/test_workspace.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/aeat_sync/__init__.py src/cadrumo/application/aeat_sync/workspace.py src/cadrumo/application/aeat_sync/tests/test_workspace.py` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/application/aeat_sync/__init__.py src/cadrumo/application/aeat_sync/workspace.py src/cadrumo/application/aeat_sync/tests/test_workspace.py` -> `pass`
- `verify:` `uv run --no-sync basedpyright src/cadrumo/application/aeat_sync/__init__.py src/cadrumo/application/aeat_sync/workspace.py src/cadrumo/application/aeat_sync/tests/test_workspace.py` -> `pass`
- `verify:` `npx --yes jscpd@4.2.0 src/cadrumo/application/aeat_sync/__init__.py src/cadrumo/application/aeat_sync/workspace.py src/cadrumo/application/aeat_sync/tests/test_workspace.py --format python --min-lines 6 --min-tokens 80 --max-size 250kb --reporters console --noTips` -> `pass`
