---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-28'
step_id: 'S80'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-28-live-iva-read-only-auth-success-surface-failures]]'
---

# `live-iva-compensation-wallet` `W09.P22.S80`

Suppressed Playwright TargetClosed cancellation noise for bounded live IVA
read-surface timeouts.

- Modified: `src/aeat/application/live/__init__.py`
- Modified: `src/aeat/application/live/test_iva_remote_state_acquisition.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`
- Modified: `.vault/audit/2026-05-28-live-iva-read-only-auth-success-surface-failures.md`

## Description

The combined live IVA remote-state capture now installs a narrow event-loop
exception filter while bounded browser read surfaces run. The filter suppresses
only Playwright `TargetClosedError` contexts produced by surface
timeout/cancellation and delegates unrelated loop exceptions to the previous or
default exception handler.

The live smoke run with an expired persisted Cl@ve session produced a typed
operator-timeout acquisition result and did not emit post-command TargetClosed
logging. That smoke run is auth-path evidence only; it did not reach the
filed-history or wallet/cartera read surfaces and is not accepted as IVA surface
evidence.

## Tests

Focused validation passed:

- `uv run ruff check src/aeat/application/live/__init__.py src/aeat/application/live/test_iva_remote_state_acquisition.py`
- `uv run pytest -q src/aeat/application/live/test_iva_remote_state_acquisition.py -q`
- Read-only live smoke with `AEAT_LIVE_IVA_SURFACE_TIMEOUT_MS=1000`, which failed closed at Cl@ve approval timeout without TargetClosed logging.
