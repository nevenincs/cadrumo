---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:7be25800521872e557ddf0f63a3dada81e48a40c82f4c19aba6b78754be883a6'
step_id: 'S378'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---


# Build the full declaration calendar as an agenda-first searchable and filterable workbench with past, upcoming, overdue, filed, and evidence-unknown scopes

## Scope

- `src/cadrumo/entrypoints/tui/declarations/calendar.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/declarations/calendar.py`
- `M` `src/cadrumo/entrypoints/tui/declarations/controller.py`
- `M` `src/cadrumo/entrypoints/tui/declarations/models.py`
- `M` `src/cadrumo/entrypoints/tui/declarations/routes.py`
- `A` `src/cadrumo/entrypoints/tui/declarations/tests/test_calendar.py`
- `M` `src/cadrumo/entrypoints/tui/declarations/tests/test_declarations_workspace.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `M` `.vault/exec/2026-08-11-tui-architecture/2026-08-11-tui-architecture-W08-P27-S378.md`
- `verify:` `uv run --no-sync pytest -q -m integration src/cadrumo/entrypoints/tui/declarations/tests/test_calendar.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/tui/declarations/calendar.py src/cadrumo/entrypoints/tui/declarations/tests/test_calendar.py` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/entrypoints/tui/declarations/calendar.py src/cadrumo/entrypoints/tui/declarations/tests/test_calendar.py` -> `pass`
- `verify:` `uv run --no-sync basedpyright src/cadrumo/entrypoints/tui/declarations/calendar.py src/cadrumo/entrypoints/tui/declarations/tests/test_calendar.py` -> `pass`
- `verify:` `npx --yes jscpd@4.2.0 src/cadrumo/entrypoints/tui/declarations/calendar.py src/cadrumo/entrypoints/tui/declarations/tests/test_calendar.py --format python --min-lines 6 --min-tokens 80 --max-size 250kb --reporters console --noTips` -> `pass`
