---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase5` `step20`

Moved deadline windows and deadline applicability out of Python support tables
and into the calculation registry.

- Modified: `registry/aeat/modelos/130.toml`
- Modified: `src/aeat/domain/calculations/registry/_ids.py`
- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/_snapshot.py`
- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/deadlines/_engine.py`
- Modified: `src/aeat/domain/deadlines/__init__.py`
- Deleted: `src/aeat/domain/deadlines/_calendar.py`
- Deleted: `src/aeat/domain/deadlines/_applies.py`
- Replaced: `src/aeat/domain/deadlines/test_engine.py`
- Deleted: `src/aeat/domain/deadlines/test_calendar.py`
- Deleted: `src/aeat/domain/deadlines/test_applies.py`

## Description

The registry schema now includes deadline windows and explicit profile
applicability conditions. Snapshot creation exposes deadline windows as a typed
subview, and registry validation checks deadline legal/source closure plus the
required deadline application link.

Modelo 130 now carries its 2026 filing windows and the direct-estimation profile
condition in TOML. The deadline engine loads and validates registry data before
computing schedules. The old in-code filing calendar and applicability rule
table were deleted.

Deadline tests now assert registry-backed temporal resolution through the
deadline engine.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry src/aeat/domain/deadlines -q`
- `uv run ruff check src/aeat/domain/calculations/registry src/aeat/domain/deadlines`
- `uv run ty check src/aeat/domain/calculations/registry src/aeat/domain/deadlines`
