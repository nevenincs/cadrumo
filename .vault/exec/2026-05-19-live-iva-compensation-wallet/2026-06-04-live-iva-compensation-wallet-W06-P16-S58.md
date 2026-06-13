---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S58'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-03-live-iva-compensation-wallet-code-review-audit]]'
---

# `live-iva-compensation-wallet` `W06.P16.S58`

## Scope

Guard tests for own-profile read navigation versus represented-taxpayer and write-class AEAT actions.

## Description

- Added remote-state guard matrix coverage for represented-taxpayer continuation, presentation, signing, payment, and confirmation browser actions.
- Added auth policy coverage proving the configured own-name representation action is allowed and an unclassified represented-taxpayer representation action is rejected.
- Re-ran existing wallet representation-form tests covering own-name dispatcher acceptance, representative radio rejection, and represented-taxpayer text rejection.

## Outcome

Passing verification:

- `pytest -q src/aeat/domain/calculations/registry/test_remote_state_guard.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/core/test_external_constants.py` -> 163 passed.
- `ruff check src/aeat/domain/calculations/registry/_remote_state_guard.py src/aeat/domain/calculations/registry/test_remote_state_guard.py src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` -> passed.

## Notes

The tests exercise production guard policy code and production auth/wallet driver helpers. They do not use live private taxpayer data and do not contact AEAT.
