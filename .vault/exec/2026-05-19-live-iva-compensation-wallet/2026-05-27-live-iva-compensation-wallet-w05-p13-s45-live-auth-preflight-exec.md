---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'W05.P13.S45'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# `live-iva-compensation-wallet` `W05.P13.S45`

Added the redacted live-auth preflight report and rendered it before IVA live
auth starts.

- Modified: `src/aeat/application/auth/_operator.py`
- Modified: `src/aeat/application/auth/__init__.py`
- Modified: `src/aeat/application/auth/test_operator.py`
- Modified: `src/aeat/entrypoints/cli/_app_live.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

The application auth layer now exposes `build_live_auth_preflight_report`, which
projects the active profile, provider, identity-readiness, Cl@ve mode, timeout,
support-number presence, certificate state, and persisted-session state without
surfacing raw taxpayer identifiers or support values. The IVA wallet live pull
and capture-history CLI paths render those fields to stderr before calling the
live acquisition backend, so the operator can verify the profile and auth
configuration before any Cl@ve approval wait begins.

Review follow-up extended the same preflight rendering to filed-history
list/capture/capture-sources, DEHu notifications capture, and expedientes
capture live-read entrypoints.

## Tests

- `uv run pytest -q src/aeat/application/auth/test_operator.py src/aeat/application/auth/test_diagnostics.py` passed.
- `uv run ruff check src/aeat/application/auth/_operator.py src/aeat/application/auth/__init__.py src/aeat/application/auth/_diagnostics.py src/aeat/application/auth/test_operator.py src/aeat/application/auth/test_diagnostics.py src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/entrypoints/cli/_app_live.py` passed.
