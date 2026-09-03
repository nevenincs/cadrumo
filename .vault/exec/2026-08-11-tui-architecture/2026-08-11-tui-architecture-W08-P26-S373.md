---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:72535d637f803cf63b09381c12faf49073454a21ecf1f69ff48dbc05e140a603'
step_id: 'S373'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Measure both candidates at supported terminal sizes, both themes, and every shipped locale for clipping, scroll ownership, focus reach, and task keystrokes

## Scope

- `src/cadrumo/entrypoints/tui/devtools/tests/test_home_candidates.py`

## Changes
- `M` `src/cadrumo/entrypoints/tui/devtools/home_candidates.py`
- `M` `src/cadrumo/entrypoints/tui/devtools/tests/test_home_candidates.py`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p26-s373-review-audit.md`
- `verify:` `uv run pytest -q -n 0 -m "" src/cadrumo/entrypoints/tui/devtools/tests/test_home_candidates.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/entrypoints/tui/devtools/home_candidates.py src/cadrumo/entrypoints/tui/devtools/tests/test_home_candidates.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/entrypoints/tui/devtools/home_candidates.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/entrypoints/tui/devtools/home_candidates.py` -> `pass`
