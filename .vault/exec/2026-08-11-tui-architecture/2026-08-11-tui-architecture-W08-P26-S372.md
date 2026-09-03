---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:30d90d3316e4e091e78b9d888ab646ede4a71e3c143693098a3767ae62999c02'
step_id: 'S372'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Implement due-driven and task-launcher prototype screens over the same immutable projection

## Scope

- `src/cadrumo/entrypoints/tui/devtools/home_candidates.py`

## Changes
- `A` `src/cadrumo/entrypoints/tui/devtools/home_candidates.py`
- `A` `src/cadrumo/entrypoints/tui/devtools/tests/test_home_candidates.py`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p26-s372-review-audit.md`
- `verify:` `uv run pytest -q -n 0 -m "" src/cadrumo/entrypoints/tui/devtools/tests/test_home_candidates.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/entrypoints/tui/devtools/home_candidates.py src/cadrumo/entrypoints/tui/devtools/tests/test_home_candidates.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/entrypoints/tui/devtools/home_candidates.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/entrypoints/tui/devtools/home_candidates.py` -> `pass`
