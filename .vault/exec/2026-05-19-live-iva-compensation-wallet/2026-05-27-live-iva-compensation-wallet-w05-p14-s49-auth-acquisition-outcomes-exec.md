---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'W05.P14.S49'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-26-live-iva-auth-read-acquisition-adr]]'
---

# `live-iva-compensation-wallet` `W05.P14.S49`

Added typed auth acquisition outcomes to the backend live IVA remote-state report.

- Modified: `src/aeat/application/live/__init__.py`
- Modified: `src/aeat/application/live/_errors.py`
- Modified: `src/aeat/application/live/test_iva_live_failure_taxonomy.py`
- Modified: `src/aeat/application/live/test_iva_remote_state_acquisition.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

`IvaRemoteStateAcquisitionReport` now carries a redacted `LiveIvaAuthOutcome`
alongside filed-history and wallet/cartera surface outcomes. Successful auth is
represented as `authenticated`; auth failures propagate their typed mode to both
downstream surfaces so no-prompt, timeout, QR, certificate-required, wrong
identity, AEAT 403, and DOM drift cannot be collapsed into a generic missing
surface. The persisted acquisition manifest and stored-evidence projection now
include the redacted auth outcome and per-surface `outcome_mode`.

Certificate-required auth gates are also classified separately from generic
AEAT 403 when Sede context declares the required provider.

## Tests

- `uv run pytest -q src/aeat/application/live/test_iva_live_failure_taxonomy.py src/aeat/application/live/test_iva_remote_state_acquisition.py -q` passed.
- `uv run ruff check src/aeat/application/live/__init__.py src/aeat/application/live/_errors.py src/aeat/application/live/test_iva_live_failure_taxonomy.py src/aeat/application/live/test_iva_remote_state_acquisition.py` passed.
