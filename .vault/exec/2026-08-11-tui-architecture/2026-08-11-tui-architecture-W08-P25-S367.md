---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:9ff9a2d36a63d1af02b91129a8c4dcfb63bcf07216fa536ac75f96141e71497a'
step_id: 'S367'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Promote the calendar evidence assembly into a frontend-neutral application provider consumed by CLI and TUI

## Scope

- `src/cadrumo/application/overview/evidence.py`

## Changes
- `M` `src/cadrumo/application/overview/evidence.py`
- `M` `src/cadrumo/application/overview/calendar_evidence.py`
- `M` `src/cadrumo/application/overview/tests/test_evidence_provider.py`
- `M` `src/cadrumo/entrypoints/cli/_overview_evidence.py`
- `M` `.vault/audit/2026-09-03-tui-architecture-w08-p25-s367-review-audit.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/application/overview/tests/test_evidence_provider.py src/cadrumo/application/overview/tests/test_calendar_filing_evidence_conflicts.py src/cadrumo/entrypoints/cli/tests/test_overview_calendar_local_evidence.py src/cadrumo/entrypoints/cli/tests/test_calendar_evidence_survives_undeclared_nif.py` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/application/overview/calendar_evidence.py src/cadrumo/application/overview/evidence.py src/cadrumo/application/overview/tests/test_evidence_provider.py src/cadrumo/entrypoints/cli/_overview_evidence.py` -> `pass`
- `verify:` `uv run ty check src/cadrumo/application/overview/calendar_evidence.py src/cadrumo/application/overview/evidence.py src/cadrumo/entrypoints/cli/_overview_evidence.py` -> `pass`
- `verify:` `uv run basedpyright src/cadrumo/application/overview/calendar_evidence.py src/cadrumo/application/overview/evidence.py src/cadrumo/entrypoints/cli/_overview_evidence.py` -> `pass`
