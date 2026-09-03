---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:67e3082a10f83fd9160912451c98fa6e140dbc844215e3d2fc12e7752fd76b29'
step_id: 'S392'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Define an immutable Declarations workspace projection from preloaded work, calculation-revision, filing-record, and sanitized lifecycle authorities

## Scope

- `src/cadrumo/application/modelo/declarations_workspace.py`

## Changes
- `A` `src/cadrumo/application/modelo/declarations_workspace.py`
- `A` `src/cadrumo/application/modelo/tests/test_declarations_workspace.py`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p27-s392-review-audit.md`
- `verify:` `uv run pytest -q -n 0 -m "" src/cadrumo/application/modelo/tests/test_declarations_workspace.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/application/modelo/declarations_workspace.py src/cadrumo/application/modelo/tests/test_declarations_workspace.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/application/modelo/declarations_workspace.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/application/modelo/declarations_workspace.py` -> `pass`
