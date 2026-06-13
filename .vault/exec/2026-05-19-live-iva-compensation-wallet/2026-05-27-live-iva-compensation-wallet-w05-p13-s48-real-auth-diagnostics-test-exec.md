---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'W05.P13.S48'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# `live-iva-compensation-wallet` `W05.P13.S48`

Added real-provider diagnostic coverage for Cl@ve auth context redaction.

- Modified: `src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

The Cl@ve Móvil auth test suite now exercises the production
`ClaveMovilAuthProvider._attempt_context` path against real active-profile
secure storage and sanitized Cl@ve settings. The test creates an active profile
through the profile storage span, records a sanitized synthetic NIE, then proves
the diagnostic context contains route, auth mode, identity kind, profile
registration, profile-record presence, profile-tax-id presence, support-number
presence, identity alignment, and timeout fields without including raw DNI/NIE
or support-number values.

## Tests

- `uv run pytest -q src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py -q` passed.
- `uv run ruff check src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` passed.
