---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:ad33e251ad18baa00a39e694614d8fda115c9c48b26708c08c05d47ecb3f443c'
step_id: 'S369'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Define the TUI destination catalogue, explicit admission states, screen-factory protocol, and semantic focus identities

## Scope

- `src/cadrumo/entrypoints/tui/navigation.py`

## Changes
- `A` `src/cadrumo/entrypoints/tui/navigation.py`
- `A` `src/cadrumo/entrypoints/tui/tests/test_navigation.py`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p25-s369-review-audit.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/entrypoints/tui/tests/test_navigation.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/entrypoints/tui/navigation.py src/cadrumo/entrypoints/tui/tests/test_navigation.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/entrypoints/tui/navigation.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/entrypoints/tui/navigation.py` -> `pass`
