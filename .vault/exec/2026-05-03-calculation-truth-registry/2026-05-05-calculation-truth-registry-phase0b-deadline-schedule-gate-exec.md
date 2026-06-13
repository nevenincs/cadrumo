---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---

# `calculation-truth-registry` `Phase 0B` `deadline-schedule-gate`

Connected registry filing schedules to deadline obligation selection.

- Modified: `registry/aeat/modelos/111.toml`
- Modified: `src/aeat/domain/deadlines/_engine.py`
- Modified: `src/aeat/domain/deadlines/_models.py`
- Modified: `src/aeat/domain/deadlines/__init__.py`
- Modified: `src/aeat/domain/deadlines/test_engine.py`
- Modified: `src/aeat/domain/calculations/registry/test_filing_schedule_selection.py`

## Description

Modelo 111 now declares monthly 2026 deadline windows alongside quarterly windows. Deadline computation filters windows through the matched registry filing schedule before applying model obligation conditions, so large-company enrollment selects monthly periods and ordinary enrollment selects quarterly periods.

The profile model now carries AEAT enrollment facts consumed by registry predicates. Schedule selection continues to use the central predicate evaluator.

## Tests

Verified registry loading and validation with `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`.

Verified behavior with `uv run pytest src\aeat\domain\deadlines\test_engine.py src\aeat\domain\deadlines\test_models.py src\aeat\domain\calculations\registry\test_filing_schedule_selection.py -q`.

Verified focused style and typing with `uv run ruff check` and `uv run ty check` on touched Python surfaces.
