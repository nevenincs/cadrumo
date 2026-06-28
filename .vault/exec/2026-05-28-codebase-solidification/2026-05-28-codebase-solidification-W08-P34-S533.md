---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S533'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W08.P34.S533`

RELOCATE: `PeriodKind(StrEnum)` from `application/aggregation/_models.py` to `aeat.core.aggregation`, then enroll the canonical import in `domain/deadlines/_engine.py` (5 string-comparison sites) and remove the local definition from the application layer.

- Modified: `src/aeat/core/aggregation.py` (added `PeriodKind`)
- Modified: `src/aeat/application/aggregation/_models.py` (removed local class; added `from ...core.aggregation import PeriodKind`)
- Modified: `src/aeat/domain/deadlines/_engine.py` (5 bare string comparisons replaced with `PeriodKind` members)

## Description

`PeriodKind` lived in the application layer but was needed by the domain deadline engine, violating hexagonal direction. Moving it to `aeat.core` makes it available to both domain and application without introducing a cross-layer dependency. The `_schema.py` `period_kind` Literal fields were intentionally left as plain `Literal["monthly", "quarterly", "annual", "ad_hoc"]` because pydantic v2 strict mode cannot coerce TOML-loaded plain strings to `StrEnum` instances when the field type is `PeriodKind | Literal["ad_hoc"]`; engine comparisons work via StrEnum value equality instead.

Grep-post-condition: `grep -n "period_kind == ['\"]" src/aeat/domain/deadlines/_engine.py` returned 0 lines.

## Tests

Existing `test_deadline_engine.py` suite and registry load tests passed.
