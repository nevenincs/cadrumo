---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:7a54c225125706675117b7644f577308d18f206aa687d63c496f3a71ad1e3c28'
step_id: 'S25'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# project prorrata declared-volume ledger divergence advisory

## Scope

- `src/aeat/application/calculations/_prorrata_regularizacion.py`

## Description

- Re-read the W04 plan row, cross-period prorrata ADR, and current
  calculation/modelo advisory split after HEAD moved.
- Confirmed S25 must keep declared annual volume casillas authoritative and must
  not promote `PRORRATA_REGULARIZACION`, `_source_mesh.py`, registry binding
  source kinds, resolver conventions, validator conventions, or registry
  selectors.
- Added `ProrrataDeclaredVolumeLedgerRollup` to carry the declared annual
  con-derecho/sin-derecho volumes beside the ledger-side annual rollup.
- Added `build_prorrata_declared_volume_divergence_advisory` to window existing
  `IvaLedgerObservation` rows with the supplied ejercicio `Period.contains`
  boundaries, classify repercutido output volume into con-derecho and
  sin-derecho buckets, and return a non-blocking `CalculationSourceDiagnostic`
  when the ledger rollup contradicts declared values.
- Kept Art. 20.Uno.26 exempt output in the con-derecho bucket, other domestic
  exempt output in the sin-derecho bucket, and input-side rows outside the
  rollup.
- Exported the projection helper through `application.calculations` and added
  focused regressions for contradiction, silence-on-match, input-row exclusion,
  and out-of-ejercicio exclusion.

## Outcome

- S25 is complete: the calculation layer now has the annual declared-volume
  versus ledger-rollup divergence advisory projection required by the plan.
- The projection is advisory-only and preserves declared volume authority; it
  records contradiction rather than substituting the ledger rollup for filed
  casillas.
- No new binding source kind, resolver convention, validator convention,
  registry selector shape, or live calculate-mesh feed was introduced.

## Notes

- Verification passed: `uv run --no-sync ruff check src\aeat\application\calculations\_prorrata_regularizacion.py src\aeat\application\calculations\__init__.py src\aeat\application\calculations\tests\test_prorrata_regularizacion.py`.
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\calculations\tests\test_prorrata_regularizacion.py -n 0` (7 passed).
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\modelo\tests\test_prorrata_regularizacion_advisory.py -n 0` (5 passed).
- Verification passed: `uv run --no-sync pytest -q src\aeat\application\calculations\tests\test_prorrata_regularizacion.py src\aeat\application\modelo\tests\test_prorrata_regularizacion_advisory.py -n 0` (12 passed).
