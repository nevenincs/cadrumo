---
tags:
  - '#exec'
  - '#schedule-predicate-catalogue'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S03'
related:
  - "[[2026-05-31-schedule-predicate-catalogue-plan]]"
---

# `schedule-predicate-catalogue` `P02.S03`

Proof test added to `test_filing_schedule_selection.py` for the
`filing_schedule` predicate surface.

- Modified: `src/aeat/domain/calculations/registry/test_filing_schedule_selection.py`

## Description

Added `test_filing_schedule_predicate_with_unknown_field_is_reported_as_contract_error`.
The test takes modelo 111 revision `2019-y-siguientes`, injects a synthetic
`ProfilePredicateDefinition` with `field="unknown_predicate_field"` into a real
`filing_schedule`'s `profile_conditions` via `model_copy`, then calls
`validate_user_profile_registry_contract([mutated_modelo], schema)` and asserts
`surface=filing_schedule`, `severity=ERROR`, `selector=unknown_predicate_field`.

## Tests

- `test_filing_schedule_selection.py`: 5 passed (4 pre-existing + 1 new), 0 failed
- Commit: 48e217bef
