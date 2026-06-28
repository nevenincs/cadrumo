---
tags:
  - '#exec'
  - '#core-authority'
step_id: S20
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P06.S20 — MODELO_720_REPORTING_THRESHOLD_EUR centralisation (RELOC-013)

## Change

Added `MODELO_720_REPORTING_THRESHOLD_EUR: Final[Decimal] = Decimal("50000.00")` to
`src/aeat/core/external_constants.py` as the single authoritative source for the
Modelo 720 per-asset-class declaration floor per AEAT instrucciones.

Removed local `THRESHOLD_720_EUR_PER_CLASS` declaration from
`src/aeat/application/aggregation/_foreign_assets.py`:
- Added import of `MODELO_720_REPORTING_THRESHOLD_EUR` from core
- Updated `declarable_asset_classes_720` to use the centralised constant
- Removed `THRESHOLD_720_EUR_PER_CLASS` from `__all__`

Also removed the stray docstring that had been orphaned after M347_THRESHOLD_EUR
in `external_constants.py`.

Updated callers:
- `test_foreign_assets.py`: imports `MODELO_720_REPORTING_THRESHOLD_EUR` from core
- Regression tests added to `test_external_constants.py`:
  value assertion, isinstance guard, module import identity check,
  anti-tautology AST scan for bare `Decimal("50000.00")` in `_foreign_assets.py`

## Verification gate

`pytest src/aeat/core/test_external_constants.py src/aeat/application/aggregation/test_foreign_assets.py -q`
— 75 passed, 0 failed.

## Commit

`67f9707d9` — const(core): centralise MODELO_720_REPORTING_THRESHOLD_EUR (RELOC-013)
