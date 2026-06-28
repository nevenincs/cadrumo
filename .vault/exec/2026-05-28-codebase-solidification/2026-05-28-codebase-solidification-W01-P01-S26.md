---
step_id: "S26"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W01.P01.S26

**Status**: closed

## What was done

Added four real-behavior tests to `src/aeat/application/calculations/test_binding_prefill.py`:

- `test_binding_prefill_type_error_is_registered_in_error_registry` — asserts `REFUSED_BINDING_PREFILL_TYPE` is in `ERROR_REGISTRY`.
- `test_binding_prefill_type_error_round_trips_through_build_error_envelope` — constructs `BindingPrefillTypeError` and asserts the envelope code and `retryable=False`.
- `test_selector_year_delta_raises_binding_prefill_type_error_for_invalid_type` — calls production `_selector_year_delta([])` with a list (invalid type) and asserts `BindingPrefillTypeError` is raised.
- `test_selector_periods_raises_binding_prefill_type_error_for_invalid_type` — calls production `_selector_periods(42)` with an int (invalid type) and asserts `BindingPrefillTypeError` is raised.

All four tests pass. No mocks, no skips, no xfail.

## Files touched

- `src/aeat/application/calculations/test_binding_prefill.py` — added imports for `ERROR_REGISTRY`, `build_error_envelope`, `_selector_year_delta`, `_selector_periods`, `BindingPrefillTypeError`; added four tests.

## Commit

`62529675a`
