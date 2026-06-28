---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S499
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W06.P30.S499

Real-behavior tests for the consolidated `_coerce_iso_date_field` helper and the three model validators that delegate to it.

- Created: `src/aeat/domain/profile/test_family_parse_date.py`

## Description

The test file covers the full input/output contract shared by all three validators:

- Direct unit tests on `_coerce_iso_date_field`: None passthrough, ISO string parse (`"2024-03-15"` -> `date(2024, 3, 15)`), date object passthrough, and `ValueError` on bad format (`"15/03/2024"`).
- Per-model integration tests on `DescendantInfo`, `RentaDescendantProfile`, and `RentaAscendantProfile`: ISO string -> date round-trip, `None` passthrough for optional date fields (`adoption_date`, `death_date`), and `ValidationError` on non-ISO input. Each model's bad-format test uses a distinct malformed string to avoid copy-paste tautology.

No mocks, no skips, no xfail. Tests exercise real pydantic validation and real `_parse_iso8601_date` logic.

## Tests

16 tests created; all 16 passed in 0.05 s (within the full 192-test profile run).
