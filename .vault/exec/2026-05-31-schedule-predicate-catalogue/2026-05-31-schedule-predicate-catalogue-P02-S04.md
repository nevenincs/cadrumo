---
tags:
  - '#exec'
  - '#schedule-predicate-catalogue'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S04'
related:
  - "[[2026-05-31-schedule-predicate-catalogue-plan]]"
---

# `schedule-predicate-catalogue` `P02.S04`

Proof test added to `test_filing_schedule_selection.py` for the
`deadline_window` predicate surface.

- Modified: `src/aeat/domain/calculations/registry/test_filing_schedule_selection.py`

## Description

Added `test_deadline_window_predicate_with_unknown_field_is_reported_as_contract_error`.
The test takes modelo 111 revision `2019-y-siguientes`, injects a synthetic
`ProfilePredicateDefinition` with `field="unknown_predicate_field"` into a real
`deadline_window`'s `applicability_conditions` via `model_copy`, then calls
`validate_user_profile_registry_contract([mutated_modelo], schema)` and asserts
`surface=deadline_window`, `severity=ERROR`, `selector=unknown_predicate_field`.

## Tests

- `test_filing_schedule_selection.py`: 6 passed (5 prior + 1 new), 0 failed
- Full gate: `test_filing_schedule_selection.py` + `test_authority.py` + `test_registry_contract.py`: 16 passed, 0 failed
- Commit: 665c38272
