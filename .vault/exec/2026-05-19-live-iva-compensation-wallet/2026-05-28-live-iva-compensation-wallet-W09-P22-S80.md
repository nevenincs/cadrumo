---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S80'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-28-live-iva-read-only-auth-success-surface-failures-audit]]'
---

# `live-iva-compensation-wallet` `W09.P22.S80`

Suppressed Playwright TargetClosed cancellation noise for bounded live IVA
read-surface timeouts.

- Modified: `src/aeat/application/live/__init__.py`
- Modified: `src/aeat/application/live/test_iva_remote_state_acquisition.py`
- Modified: `src/aeat/core/config.py`
- Modified: `env/.env.example`
- Modified: `src/aeat/locales/hu.yml`
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

2026-06-02 follow-up: after the codebase shifted toward a more centralized live
backend, another read-only capture exposed Playwright `net::ERR_ABORTED`
frame-detach cancellation logging during command shutdown. The implementation
now treats that report as cancellation-only noise alongside `TargetClosedError`,
keeps the cancellation handler installed through the combined capture command's
event-loop teardown, and centralizes the drain delay in `Settings` with an
`.env.example` entry.

The follow-up did not submit data to AEAT. A short read-only live smoke reused a
persisted Cl@ve session, failed closed with typed read-surface timeouts, and
produced no post-command cancellation logging. This remains shutdown-hygiene
evidence only; accepted live IVA data extraction remains open under S56/S77.

## Tests

Focused validation passed:

- `uv run ruff check src/aeat/application/live/__init__.py src/aeat/application/live/test_iva_remote_state_acquisition.py`
- `uv run pytest -q src/aeat/application/live/test_iva_remote_state_acquisition.py -q`
- Read-only live smoke with `AEAT_LIVE_IVA_SURFACE_TIMEOUT_MS=1000`, which failed closed at Cl@ve approval timeout without TargetClosed logging.

2026-06-02 follow-up validation passed:

- `.venv\Scripts\python.exe -m ruff check src/aeat/application/live/__init__.py src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/core/config.py`
- `.venv\Scripts\python.exe -m pytest -q src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/application/live/test_iva_live_failure_taxonomy.py src/aeat/tests/test_config.py -q`
- `.venv\Scripts\python.exe -m aeat.locales audit`
- Read-only live smoke with `AEAT_LIVE_IVA_SURFACE_TIMEOUT_MS=1000` and `AEAT_LIVE_IVA_CANCELLATION_DRAIN_MS=500`, which reused a persisted Cl@ve session and returned typed surface timeouts without post-command cancellation logging.
