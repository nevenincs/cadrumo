---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:bf213c3ca86780d045dde0dc0d67d1365a3c8d346e3b3da690a984f39de0c03d'
step_id: 'S33'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# emit missing prorrata carry advisory

## Scope

- `src/aeat/application/calculations/__init__.py`
- `src/aeat/application/calculations/_prorrata_regularizacion.py`
- `src/aeat/application/modelo/_calculation_diagnostics.py`
- `src/aeat/application/modelo/_prorrata_regularizacion_advisory.py`
- `src/aeat/application/modelo/tests/test_prorrata_regularizacion_advisory.py`
- `src/aeat/application/calculations/tests/test_prorrata_missing_carry.py`

## Description

- Re-read the live plan status and confirmed `W05.P08.S33` was the next open
  step after S32.
- Re-grounded the step through semantic search, the prorrata register seed and
  service APIs, the current S32 applicability projection, and the W05 plan row.
- Added `build_prorrata_missing_provisional_advisory`, which returns a
  `PRORRATA_REGULARIZACION` source diagnostic whenever prorrata applies but the
  provisional percentage ladder is unresolved.
- Made the diagnostic name the correct operator action: record the
  inicio-de-actividad percentage for a first ejercicio, or seed/record the prior
  definitive percentage for later ejercicios.
- Exported the helper through the calculation facade and wired the
  post-calculation prorrata advisory collector to load the profile-scoped
  prorrata register by bucket, derive applicability, and emit the missing-carry
  diagnostic on non-settlement periods as well as settlement periods.
- Preserved the existing settlement regularización advisory: when the prior
  definitive percentage exists, the calculate path can still emit the proposed
  casilla-44 diagnostic alongside the missing-register carry diagnostic; when
  no prior evidence exists, the new canonical missing-carry advisory replaces
  the older pending warning on bucket-backed calculate runs.
- Added a focused test file covering prior-definitive guidance, first-ejercicio
  guidance, silence when prorrata does not apply, and silence when the ladder
  resolves.
- Added a real encrypted-runtime collector regression proving a 1T active
  `general` prorrata register entry with no provisional percentage emits the
  missing-carry diagnostic instead of staying silent.

## Outcome

- S33 is complete: applicable-but-unresolved prorrata now has a reusable
  calculation-layer advisory builder and live post-calculation wiring instead
  of a silent default.
- The helper does not fabricate a percentage and does not promote a source kind;
  it emits the visible missing-carry diagnostic through the existing Modelo 303
  advisory fan-out while leaving source-kind promotion and source-mesh resolver
  changes untouched.

## Notes

- Verification passed: `uv run --no-sync ruff check
  src\aeat\application\calculations\__init__.py
  src\aeat\application\calculations\_prorrata_regularizacion.py
  src\aeat\application\calculations\tests\test_prorrata_missing_carry.py
  src\aeat\application\modelo\_calculation_diagnostics.py
  src\aeat\application\modelo\_prorrata_regularizacion_advisory.py
  src\aeat\application\modelo\tests\test_prorrata_regularizacion_advisory.py`.
- Verification passed: `uv run --no-sync pytest -q
  src\aeat\application\calculations\tests\test_prorrata_missing_carry.py
  src\aeat\application\modelo\tests\test_prorrata_regularizacion_advisory.py -n 0`
  (10 passed).
- Verification passed: `uv run --no-sync pytest -q
  src\aeat\application\calculations\tests\test_prorrata_applicability.py
  src\aeat\application\calculations\tests\test_prorrata_regularizacion.py -n 0`
  (14 passed).
