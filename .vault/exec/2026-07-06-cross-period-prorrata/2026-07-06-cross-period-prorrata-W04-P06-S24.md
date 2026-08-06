---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:e3189943600502ac4f23bc1831538f0a7b37d53f9e38ab858f8fb879cc476472'
step_id: 'S24'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# feed M303 casilla 44 and M390 regularizacion projection

## Scope

- `src/aeat/application/calculations/_prorrata_regularizacion.py`

## Description

- Re-read the W04 plan row, cross-period prorrata ADR, scope ADR, and current
  prorrata regularizacion advisory implementation after HEAD moved.
- Confirmed `PRORRATA_REGULARIZACION` is still intentionally deferred and that
  S24 must not promote `_source_mesh.py` or add a new source kind, resolver
  convention, validator convention, or registry selector shape.
- Added `ProrrataRegularizacionFeedProjection` and
  `project_prorrata_regularizacion_feed` to project the existing
  `compute_regularizacion_prorrata_anual` result onto both the proposed Modelo
  303 casilla 44 value and the Modelo 390 annual regularizacion value.
- Kept the definitive percentage as a caller-supplied registry-derived value:
  the helper does not recompute the prorrata percentage from volume casillas and
  therefore preserves the declared-volume registry authority.
- Rewired `build_prorrata_regularizacion_advisory` to consume the structured
  projection while keeping its public return shape unchanged.
- Exported the projection helper through `application.calculations` and added a
  focused regression proving the M303 and M390 proposed values are a single
  projection of the same regularizacion result.

## Outcome

- S24 is complete: the settlement regularizacion projection now carries a
  structured proposed feed for Modelo 303 casilla 44 and the Modelo 390 annual
  regularizacion field, while the deferred source-kind promotion remains gated
  for S30.
- The change is intentionally not a live mesh binding and does not alter the
  registry tree, source-kind taxonomy, resolver conventions, or validator
  conventions.
- The focused regression avoids a new hand-computed legal expected value; it
  asserts that both filing targets are sourced from the single existing domain
  result, leaving the end-to-end AEAT Manual oracle proof to S28 as planned.

## Notes

- Verification passed: `uv run --no-sync ruff check src\aeat\application\calculations\_prorrata_regularizacion.py src\aeat\application\calculations\__init__.py src\aeat\application\calculations\tests\test_prorrata_regularizacion.py`.
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\calculations\tests\test_prorrata_regularizacion.py -n 0` (5 passed).
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\modelo\tests\test_prorrata_regularizacion_advisory.py -n 0` (5 passed).
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\calculations\tests\test_prorrata_regularizacion.py src\aeat\application\modelo\tests\test_prorrata_regularizacion_advisory.py -n 0` (10 passed).
