---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-11'
step_id: 'S355'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Remove ART_20_UNO_26, its full-deduction/casilla-61 prose, and the special prorrata-numerator route so Article 20 exempt operations use the generic DOMESTIC_EXEMPT path

## Scope

- `src/aeat/{domain/iva/_schema.py`
- `application/calculations/_prorrata_regularizacion.py`
- `application/calculations/tests/test_prorrata_regularizacion.py}`

## Description

- Remove the unsupported `ART_20_UNO_26` member and every current full-deduction or Modelo 303 casilla-61 claim.
- Route every repercutido `DOMESTIC_EXEMPT` observation through the existing `sin_derecho` prorrata side.
- Retain the other Article 20 discriminator members, generic category validation, and generic ledger-selector behavior.
- Replace obsolete member fixtures with lawful retained members and remove the false special-route fixture without adding the separate S444 regression.

## Outcome

The Article 20.Uno.26 deduction-right exception no longer exists in production code. Domestic exempt observations now keep the generic exempt-operation treatment, and no Modelo 303 route was added or inferred.

Focused verification passed: `uv run --no-sync ruff check` on the eight changed source/test files and `uv run --no-sync pytest -q` on the five affected modules (`115 passed`).

## Notes

An unrelated concurrent settlement-period change was already present in `_prorrata_regularizacion.py`; it was neither modified nor included in this Step's intended change.
