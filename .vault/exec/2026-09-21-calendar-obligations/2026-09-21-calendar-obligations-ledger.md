---
tags:
  - '#exec'
  - '#calendar-obligations'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:152a20639e58be2c5b990274881328517d6021e3e6625c33266b1e1f6cabd941'
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
- `S04` `M` `src/cadrumo/application/modelo/declarations_calendar.py`
- `S04` `M` `src/cadrumo/application/modelo/tests/test_declarations_calendar.py`
- `S04` `M` `src/cadrumo/entrypoints/tui/declarations/tests/calendar_fixtures.py`
- `S04` `verify:` `uv run pytest -n 0 declarations calendar application and TUI` -> `pass`
- `S04` `verify:` `uv run ruff check declarations calendar files` -> `pass`
- `S04` `verify:` `uv run ruff and ty check declarations calendar` -> `pass`
- `S05` `M` `src/cadrumo/application/overview/tests/test_calendar.py`
- `S05` `M` `.agents/session-briefs/handoffs/2026-09-21-calendar-obligations-checkpoint.md`
- `S05` `verify:` `uv run pytest src/cadrumo/application/overview/tests/test_calendar.py -q` -> `pass`
- `S06` `M` `src/cadrumo/application/modelo/declarations_calendar.py`
- `S06` `M` `src/cadrumo/application/modelo/work_plazo.py`
- `S06` `M` `src/cadrumo/application/modelo/tests/test_declarations_calendar.py`
- `S06` `verify:` `uv run ruff check src/cadrumo/application/modelo/declarations_calendar.py src/cadrumo/application/modelo/work_plazo.py src/cadrumo/application/modelo/tests/test_declarations_calendar.py` -> `pass`
- `S07` `M` `src/cadrumo/entrypoints/cli/_overview_payloads.py`
- `S07` `M` `src/cadrumo/entrypoints/cli/_overview_rendering.py`
- `S07` `M` `src/cadrumo/entrypoints/cli/tests/test_overview_calendar_verb.py`
- `S07` `verify:` `uv run ruff check src/cadrumo/entrypoints/cli/_overview_payloads.py src/cadrumo/entrypoints/cli/_overview_rendering.py src/cadrumo/entrypoints/cli/tests/test_overview_calendar_verb.py` -> `pass`
- `S08` `M` `src/cadrumo/entrypoints/tui/declarations/calendar.py`
- `S08` `M` `src/cadrumo/entrypoints/tui/declarations/controller.py`
- `S08` `M` `src/cadrumo/entrypoints/tui/declarations/tests/test_calendar.py`
- `S08` `M` `src/cadrumo/locales/en/common.yml`
- `S08` `M` `src/cadrumo/locales/es/common.yml`
- `S08` `M` `src/cadrumo/locales/ca/common.yml`
- `S08` `M` `src/cadrumo/locales/hu/common.yml`
- `S08` `verify:` `uv run ruff check src/cadrumo/entrypoints/tui/declarations/calendar.py src/cadrumo/entrypoints/tui/declarations/controller.py src/cadrumo/entrypoints/tui/declarations/tests/test_calendar.py` -> `pass`
- `S09` `A` `dev/acceptance/calendar/__init__.py`
- `S09` `A` `dev/acceptance/calendar/tests/__init__.py`
- `S09` `A` `dev/acceptance/calendar/tests/test_parity.py`
- `S09` `verify:` `bounded declarations TUI suite (18 tests)` -> `pass`

## Notes

- `S09` Live AEAT and notification-content capabilities NOT EXERCISED
