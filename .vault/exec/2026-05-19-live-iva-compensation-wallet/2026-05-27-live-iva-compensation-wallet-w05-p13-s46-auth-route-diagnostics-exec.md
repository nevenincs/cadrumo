---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-27'
modified: '2026-07-31'
body_hash: 'sha256:2e2d406f3e2cd70e190cbed4ca38a3a5706176f0a70dc655d9417f337f14d69c'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# `live-iva-compensation-wallet` `W05.P13.S46`

Added explicit Cl@ve route diagnostics for live auth attempts.

- Modified: `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`
- Modified: `src/aeat/application/auth/_diagnostics.py`
- Modified: `src/aeat/application/auth/test_diagnostics.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

The Cl@ve Móvil provider now records the selected auth route in its attempt
context as either `clave_movil_non_qr_request` or
`clave_movil_qr_request`. Encrypted auth diagnostics expose that route through
the redacted diagnostic summary/detail models, and the provider start log now
records the route, mode, identity kind, identity alignment, active-profile tax
id presence, and headless state without raw DNI/NIE or support-number values.

## Tests

- `uv run pytest -q src/aeat/application/auth/test_operator.py src/aeat/application/auth/test_diagnostics.py` passed.
- `uv run ruff check src/aeat/application/auth/_operator.py src/aeat/application/auth/__init__.py src/aeat/application/auth/_diagnostics.py src/aeat/application/auth/test_operator.py src/aeat/application/auth/test_diagnostics.py src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/entrypoints/cli/_app_live.py` passed.
