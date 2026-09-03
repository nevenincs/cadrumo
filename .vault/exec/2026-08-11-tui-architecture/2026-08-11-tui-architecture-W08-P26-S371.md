---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:1f596c01a5b035608771177086767b2bd6563d0d6d109444e1ac80e811a48f01'
step_id: 'S371'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Build synthetic non-sensitive Home projections covering ready, locked, stale, never-captured, unavailable, empty, and blocked states

## Scope

- `src/cadrumo/entrypoints/tui/devtools/home_fixtures.py`

## Changes
- `A` `src/cadrumo/entrypoints/tui/devtools/home_fixtures.py`
- `A` `src/cadrumo/entrypoints/tui/devtools/tests/test_home_fixtures.py`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p26-s371-review-audit.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/entrypoints/tui/devtools/tests/test_home_fixtures.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/entrypoints/tui/devtools/home_fixtures.py src/cadrumo/entrypoints/tui/devtools/tests/test_home_fixtures.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/entrypoints/tui/devtools/home_fixtures.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/entrypoints/tui/devtools/home_fixtures.py` -> `pass`
