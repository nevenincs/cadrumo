---
step_id: S20
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S20 — AuthDiagnosticPhoneStateError test coverage

## Outcome

Extended `src/aeat/application/auth/test_diagnostics.py` with three assertions:

- The existing `pytest.raises(ValueError)` guard updated to
  `pytest.raises(AuthDiagnosticPhoneStateError)` with a context assertion
  verifying `{"phone_state": "guessed"}`.
- `test_auth_diagnostic_phone_state_error_is_in_error_registry`: asserts
  `"REFUSED_AUTH_DIAGNOSTIC_PHONE_STATE" in ERROR_REGISTRY`.
- `test_auth_diagnostic_phone_state_error_round_trips_through_build_error_envelope`:
  constructs the error, calls `build_error_envelope`, asserts code, category,
  and non-empty message.

All three tests exercise the real diagnostic path and real error registry — no
mocks, no skips.

## Files touched

- `src/aeat/application/auth/test_diagnostics.py`

## Verification

`uv run --no-sync pytest src/aeat/application/auth/test_diagnostics.py -xvs`
— 3 passed in 1.91s. Commit SHA: a184582de.
