---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S498
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W06.P30.S498

Consolidate three identical `_parse_date` validator wrappers in `src/aeat/domain/profile/family.py` into a single module-level helper.

- Modified: `src/aeat/domain/profile/family.py`

## Description

`DescendantInfo`, `RentaDescendantProfile`, and `RentaAscendantProfile` each carried an identical `@field_validator` `_parse_date` classmethod that simply delegated to `_parse_iso8601_date`. A module-level function `_coerce_iso_date_field(value: object) -> object` was extracted above the class definitions. All three validators now consist of a single `return _coerce_iso_date_field(value)` delegation call. The underlying `_parse_iso8601_date` import from `...core.parsing._dates` is unchanged; no callers outside `family.py` are affected.

Signature: `def _coerce_iso_date_field(value: object) -> object`

## Tests

192 tests in `src/aeat/domain/profile/` passed — 0 regressions.
