---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S60'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# live-iva-compensation-wallet W07.P17.S60

Scope: profile-bound secure storage for live IVA evidence and decisions.

## Description

- Audit standalone and combined live IVA capture entrypoints for storage-span drift.
- Require `capture_iva_compensation_history` to open the active profile storage span before live auth and persistence.
- Require `capture_iva_compensation_wallet` to open the active profile storage span before live auth and persistence.
- Replace combined `capture_iva_remote_state` sessionless fallback with the same active profile storage span.
- Add no-active-profile tests for standalone history capture, standalone wallet capture, and combined remote-state capture.
- Run focused storage-drift, acquisition, wallet backend, and parser/history tests.

## Outcome

Live IVA capture now fails closed before AEAT contact when no active profile storage runtime is available. Existing injected-repository wallet coverage continues to prove reconciliation decisions stay bound to the caller's repository when an explicit secure-object repository is supplied.

Verification passed:

- `python -m pytest -q src/aeat/application/live/test_iva_remote_state_acquisition.py::test_remote_state_capture_refuses_without_active_profile src/aeat/application/live/test_iva_remote_state_acquisition.py::test_standalone_iva_wallet_capture_refuses_without_active_profile src/aeat/application/live/test_iva_remote_state_acquisition.py::test_standalone_iva_history_capture_refuses_without_active_profile`
- `python -m pytest -q src/aeat/application/live/test_filed_capture_calculation_history.py src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/application/live/test_iva_wallet_capture_backend.py`
- `python -m ruff check src/aeat/application/live/__init__.py src/aeat/application/live/test_iva_remote_state_acquisition.py`

## Notes

No live AEAT request was made by the new fail-closed tests. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.
