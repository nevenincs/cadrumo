---
step_id: S08
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S08 — IVA compensation modelo error tests

## Outcome

Added three real-behavior tests to
`src/aeat/application/calculations/test_iva_compensation_history.py`:

- `test_iva_compensation_modelo_error_is_registered_in_error_registry` — asserts
  `REFUSED_IVA_COMPENSATION_MODELO` is present in `ERROR_REGISTRY`.
- `test_iva_compensation_modelo_error_round_trips_through_build_error_envelope` — constructs
  the exception and asserts the `ErrorEnvelope` carries the correct code,
  `retryable=False`, and the registered suggestion.
- `test_iva_compensation_state_from_filed_observation_raises_for_non_303_modelo` — constructs
  a real `FiledDeclaracionObservation` with `modelo="130"` and asserts
  `pytest.raises(IvaCompensationModeloError)` from the production function.

No mocks, no skips, no xfail. All 10 tests in the module pass.

## Files touched

- `src/aeat/application/calculations/test_iva_compensation_history.py`

## Pytest outcome

```
10 passed in 2.08s
```

## Commit

`0b1518aa7`
