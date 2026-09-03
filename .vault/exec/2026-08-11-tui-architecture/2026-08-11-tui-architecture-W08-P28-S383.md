---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:b76cbd157b950e39fc56261cc7c132fcaf2fb3b9f6d29fe01278db84c4de1d7f'
step_id: 'S383'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Compose the root destination stack, account header, semantic focus restoration, session expiry, and post-journey Home refresh

## Scope

- `src/cadrumo/entrypoints/tui/app.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/app.py`
- `A` `src/cadrumo/entrypoints/tui/tests/test_app.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `M` `.vault/exec/2026-08-11-tui-architecture/2026-08-11-tui-architecture-W08-P28-S383.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/entrypoints/tui/tests/test_app.py src/cadrumo/entrypoints/tui/tests/test_launcher_entry_point.py src/cadrumo/entrypoints/tui/tests/test_home.py src/cadrumo/entrypoints/tui/tests/test_search.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/tui/app.py src/cadrumo/entrypoints/tui/tests/test_app.py` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/entrypoints/tui/app.py src/cadrumo/entrypoints/tui/tests/test_app.py` -> `pass`
- `verify:` `uv run --no-sync basedpyright src/cadrumo/entrypoints/tui/app.py src/cadrumo/entrypoints/tui/tests/test_app.py` -> `pass`
- `verify:` `npx --yes jscpd@4.2.0 src/cadrumo/entrypoints/tui/app.py src/cadrumo/entrypoints/tui/tests/test_app.py --format python --min-lines 6 --min-tokens 80 --max-size 250kb --reporters console --noTips` -> `pass`
