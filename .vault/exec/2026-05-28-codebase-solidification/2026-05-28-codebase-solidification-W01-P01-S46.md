---
step_id: S46
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S46 — DiagnosticModelError real-behavior tests

## Outcome

Added 8 real-behavior tests to `src/aeat/application/test_diagnostics.py`:

- `test_diagnostic_model_error_is_registered_in_error_registry` — asserts
  `get_registered_error_code(DiagnosticModelError).code` is in `ERROR_REGISTRY`.
- `test_diagnostic_model_error_round_trips_through_build_error_envelope` — builds a
  real `DiagnosticModelError` and asserts envelope code equals
  `REFUSED_DIAGNOSTIC_MODEL_INVARIANT`.
- `test_diagnostic_check_both_recovery_fields_raises_diagnostic_model_error` — constructs
  a `DiagnosticCheck` with both `next_action` and `dead_end` and asserts the pydantic
  `ValidationError` wraps a `DiagnosticModelError` with matching message.
- `test_diagnostic_check_fail_without_recovery_raises_diagnostic_model_error` — same
  pattern for the missing-recovery-field invariant on a `fail` row.
- `test_diagnostic_check_warn_without_recovery_raises_diagnostic_model_error` — same for
  a `warn` row.
- `test_diagnostic_check_ok_with_next_action_raises_diagnostic_model_error` — ok row with
  `next_action` triggers the third invariant arm.
- `test_diagnostic_check_ok_with_dead_end_raises_diagnostic_model_error` — ok row with
  `dead_end` triggers the third invariant arm.
- `test_diagnostic_model_error_is_subclass_of_value_error` — legacy catch compatibility.

All 35 tests in `test_diagnostics.py` pass (`uv run --no-sync pytest src/aeat/application/test_diagnostics.py -xvs`).

## Files

- `src/aeat/application/test_diagnostics.py` (8 new tests appended)
