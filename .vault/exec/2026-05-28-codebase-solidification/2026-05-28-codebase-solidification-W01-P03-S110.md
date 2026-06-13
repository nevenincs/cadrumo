---
step_id: S110
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S110 — DT12/SAL computation error localization tests

## Outcome

Added two real-behavior tests to `src/aeat/entrypoints/cli/test_modelo.py`:

- `test_dt12_computation_error_locale_key_interpolates_message`: calls
  `_compute_dt12_reduccion_plan_pensiones` with `aportaciones_totales=0` (which raises
  a real ValueError), then passes the exception message to
  `tr("cli.app.modelo.work.dt12_computation_error", message=...)` and asserts the
  rendered string contains the original message — proving the `%{message}` slot wires
  through.
- `test_sal_computation_error_locale_key_interpolates_message`: same pattern with
  `_compute_sal_reserva_especial_dotacion(capital_social=0)` and the SAL locale key.

Both tests exercise real computation functions with real exception paths and real `tr()`
locale resolution. No mocks.

## Files touched

- `src/aeat/entrypoints/cli/test_modelo.py`

## Verification

`uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo.py::test_dt12_computation_error_locale_key_interpolates_message src/aeat/entrypoints/cli/test_modelo.py::test_sal_computation_error_locale_key_interpolates_message -v`
→ 2 passed.
