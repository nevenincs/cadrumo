---
step_id: "S28"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P01.S28

**Status**: closed

## What was done

Created `src/aeat/application/wizard/test_setup_answers.py` with 17 real-behavior tests:

- `test_wizard_answer_type_error_is_registered_in_error_registry` — asserts `REFUSED_WIZARD_ANSWER_TYPE` is present in `ERROR_REGISTRY`.
- `test_wizard_answer_type_error_round_trips_through_build_error_envelope` — constructs a `WizardAnswerTypeError`, calls `build_error_envelope`, asserts `code == "REFUSED_WIZARD_ANSWER_TYPE"` and `retryable is False`.
- 15 per-field tests, one per migrated raise site, calling the `@classmethod` validator methods directly on `SetupAnswers` with an invalid-type input. Direct calls exercise the production raise site without pydantic's `ValidationError` wrapping.

The `_parse_sex_code` and `_parse_disability_grade` validators each cover two fields (taxpayer + spouse), so the 13 raise sites in 12 validator methods map to 15 tests with the shared-validator cases covered by distinct inputs.

All 17 tests pass. No mocks, no skips, no xfail, no tautological assertions.

## Files touched

- `src/aeat/application/wizard/test_setup_answers.py` — created (17 tests)

## Commit

`fb551c34f`
