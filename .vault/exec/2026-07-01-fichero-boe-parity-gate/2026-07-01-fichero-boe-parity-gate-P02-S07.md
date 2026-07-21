---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-01'
modified: '2026-07-17'
step_id: 'S07'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# Unit-test the applicable-required restriction drops disposition-suppressed casillas

## Scope

- `src/aeat/application/filing/tests/test_export_applicable_required_set.py`

## Description

- Add a Modelo 303 layout-level suppression test: the DID (refund) page casillas are representable under a refund disposition header (`D`) but not under a non-refund header (`I`), and non-refund representability is always a subset of refund representability.

## Outcome

Passes as part of the four-test P02 suite. Exercises suppression without needing a full 303 draft, since the helper takes only layout + headers + provider.

## Notes

Confirms the disposition-aware applicable restriction: casillas that only apply under an unselected disposition are excluded from the required set, so the gate does not false-panic on a legitimately-absent refund page.
