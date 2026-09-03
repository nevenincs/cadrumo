---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:8b74e45b71e9ae54e062d9406944ffb4853ed2f6f426d6f60cbd94269efb6050'
step_id: 'S381'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Build the responsive Home screen from the selected projection-only candidate with status, next actions, Ledger readiness, resumable declarations, and filing agenda

## Scope

- `src/cadrumo/entrypoints/tui/home.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/home.py`
- `M` `src/cadrumo/entrypoints/tui/devtools/home_candidates.py`
- `A` `src/cadrumo/entrypoints/tui/tests/test_home.py`
- `M` `src/cadrumo/application/overview/home.py`
- `M` `src/cadrumo/application/overview/tests/test_home_projection.py`
- `verify:` `uv run pytest -q -n 0 -m "" src/cadrumo/entrypoints/tui/tests/test_home.py` -> `pass`
- `verify:` `uv run pytest -q -n 0 -m "" src/cadrumo/entrypoints/tui/devtools/tests/test_home_candidates.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/entrypoints/tui/home.py src/cadrumo/entrypoints/tui/devtools/home_candidates.py src/cadrumo/entrypoints/tui/tests/test_home.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/entrypoints/tui/home.py src/cadrumo/entrypoints/tui/devtools/home_candidates.py src/cadrumo/entrypoints/tui/tests/test_home.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/entrypoints/tui/home.py src/cadrumo/entrypoints/tui/devtools/home_candidates.py src/cadrumo/entrypoints/tui/tests/test_home.py` -> `pass`
- `verify:` `uv run pytest -q -n 0 -m "" src/cadrumo/application/overview/tests/test_home_projection.py src/cadrumo/application/overview/tests/test_home.py src/cadrumo/entrypoints/tui/tests/test_home.py` -> `pass` (32 tests)
- `verify:` `uv run ruff check src/cadrumo/application/overview/home.py src/cadrumo/application/overview/tests/test_home_projection.py src/cadrumo/application/overview/tests/test_home.py src/cadrumo/entrypoints/tui/home.py src/cadrumo/entrypoints/tui/tests/test_home.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/application/overview/home.py src/cadrumo/application/overview/tests/test_home_projection.py src/cadrumo/application/overview/tests/test_home.py src/cadrumo/entrypoints/tui/home.py src/cadrumo/entrypoints/tui/tests/test_home.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/application/overview/home.py src/cadrumo/application/overview/tests/test_home_projection.py src/cadrumo/application/overview/tests/test_home.py src/cadrumo/entrypoints/tui/home.py src/cadrumo/entrypoints/tui/tests/test_home.py` -> `pass`
