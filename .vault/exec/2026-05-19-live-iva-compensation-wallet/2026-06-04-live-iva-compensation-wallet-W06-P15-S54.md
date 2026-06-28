---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S54'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# live-iva-compensation-wallet W06.P15.S54

Scope: distinct filed-history and wallet/cartera acquisition outcomes.

## Description

- Re-audit `build_iva_remote_state_acquisition_report` and `_surface_outcome`.
- Verify tests preserve filed-history success when wallet/cartera fails.
- Verify tests keep wallet/cartera failure typed instead of collapsing it into zero-balance or success.
- Verify persisted acquisition manifests carry redacted per-surface outcome summaries.
- Run the focused remote-state acquisition suite with the new multiyear filed-history coverage.

## Outcome

The filed-history and wallet/cartera surfaces remain independent in the backend report model and persisted manifest. Existing coverage proves wallet/cartera failure does not discard filed-history evidence, auth failure is distinct from per-surface failure, and redacted manifest reload preserves per-surface status.

Verification passed:

- `python -m pytest -q src/aeat/application/live/test_filed_capture_calculation_history.py src/aeat/application/live/test_iva_remote_state_acquisition.py`
- `python -m ruff check src/aeat/application/live/test_filed_capture_calculation_history.py`

## Notes

No AEAT filing, payment, confirmation, represented-taxpayer selection, or other write path was executed.
