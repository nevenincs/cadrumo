---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S53'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# live-iva-compensation-wallet W06.P15.S53

Scope: backend read-only remote IVA acquisition orchestration.

## Description

- Re-audit `capture_iva_remote_state` and `_capture_iva_remote_state_for_active_storage`.
- Confirm one authenticated AEAT session is acquired before filed-history and wallet/cartera reads.
- Confirm auth failure returns a typed acquisition report and does not attempt either surface.
- Confirm filed-history and wallet/cartera surface errors are captured independently.
- Add non-private multiyear parser-to-reload regression coverage through `test_filed_capture_calculation_history.py`.
- Run focused application live-acquisition pytest coverage.

## Outcome

The backend orchestration retains the intended read-only shape: one authenticated session feeds both surfaces, auth failure blocks both surfaces, and each surface returns independent success or typed failure. The new regression broadens the non-private evidence chain by proving parsed Modelo 303 submitted-file history reloads as profile-local remote IVA state.

Verification passed:

- `python -m pytest -q src/aeat/application/live/test_filed_capture_calculation_history.py src/aeat/application/live/test_iva_remote_state_acquisition.py`
- `python -m ruff check src/aeat/application/live/test_filed_capture_calculation_history.py`

## Notes

No live AEAT write path was executed. No private taxpayer value was committed as a fixture or test oracle.
