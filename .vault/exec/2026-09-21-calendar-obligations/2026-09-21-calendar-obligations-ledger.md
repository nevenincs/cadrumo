---
tags:
  - '#exec'
  - '#calendar-obligations'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:ba5d59f40ad0f5cc4f0cfb487bc3fdd9e29a483fdd9ba41da62a7c0f1e5d5e10'
related:
  - "[[2026-09-21-calendar-obligations-plan]]"
---

# `calendar-obligations` ledger

## Changes

- `S01` `M` `src/cadrumo/domain/deadlines/engine.py`
- `S01` `M` `src/cadrumo/application/overview/calendar_models.py`
- `S01` `M` `src/cadrumo/application/overview/calendar.py`
- `S01` `M` `src/cadrumo/application/overview/tests/test_calendar.py`
- `S01` `M` `src/cadrumo/application/overview/tests/test_home.py`
- `S01` `M` `src/cadrumo/application/overview/tests/test_calendar_filing_evidence.py`
- `S01` `M` `src/cadrumo/application/modelo/tests/test_declarations_calendar.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/tests/workbench_fixtures.py`
- `S01` `A` `.vault/plan/2026-09-21-calendar-obligations-plan.md`
- `S01` `A` `.vault/index/calendar-obligations.index.md`
- `S01` `verify:` `uv run ty check calendar deadline files` -> `pass`
- `S02` `M` `src/cadrumo/application/overview/calendar.py`
- `S02` `M` `src/cadrumo/application/overview/tests/test_calendar.py`
- `S02` `M` `.vault/plan/2026-09-21-calendar-obligations-plan.md`
- `S02` `M` `.vault/index/calendar-obligations.index.md`
- `S02` `verify:` `uv run ty check calendar.py` -> `pass`
- `S02` `verify:` `uv run pytest -n 0 test_calendar.py` -> `pass`
- `S02` `verify:` `uv run ruff check calendar files` -> `pass`
- `S03` `M` `src/cadrumo/domain/deadlines/engine.py`
- `S03` `M` `src/cadrumo/domain/deadlines/tests/test_activity_window_gate.py`
- `S03` `M` `.vault/plan/2026-09-21-calendar-obligations-plan.md`
- `S03` `M` `.vault/index/calendar-obligations.index.md`
- `S03` `verify:` `uv run pytest -n 0 deadline engine lifecycle tests` -> `pass`
- `S03` `verify:` `uv run ruff check deadline lifecycle files` -> `pass`
- `S03` `verify:` `uv run ty check deadline engine` -> `pass`
- `S03` `verify:` `uv run pytest -n 0 deadline engine lifecycle rereview` -> `pass`
- `S03` `A` `.vault/audit/2026-09-21-calendar-obligations-audit.md`
