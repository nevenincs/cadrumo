---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:cc4930a9ba4015ea7224f191024f38496512dc4b8050e1e2d541ae200fb7e023'
step_id: 'S393'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Define a safe full Declarations calendar projection that preserves legal schedule, local filing, AEAT evidence, and source availability as independent axes

## Scope

- `src/cadrumo/application/modelo/declarations_calendar.py`

## Changes
- `A` `src/cadrumo/application/modelo/declarations_calendar.py`
- `A` `src/cadrumo/application/modelo/tests/test_declarations_calendar.py`
- `A` `.vault/audit/2026-09-03-tui-architecture-w08-p27-s393-review-audit.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/modelo/tests/test_declarations_calendar.py src/cadrumo/application/overview/tests/test_evidence_provider.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/application/modelo/declarations_calendar.py src/cadrumo/application/modelo/tests/test_declarations_calendar.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/application/modelo/declarations_calendar.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/application/modelo/declarations_calendar.py` -> `pass`
