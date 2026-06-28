---
tags:
  - '#exec'
  - '#core-authority'
step_id: S19
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P06.S19 — M347_THRESHOLD_EUR centralisation (MERGE-001)

## Change

Added `M347_THRESHOLD_EUR: Final[Decimal] = Decimal("3005.06")` to
`src/aeat/core/external_constants.py` as the single authoritative source
for the Modelo 347 declaration floor per RD 1065/2007 art. 31.1.

Removed local declarations from:
- `src/aeat/domain/modelos/_row_models.py` (was `M347_THRESHOLD_EUR: Decimal`)
- `src/aeat/application/aggregation/_counterpart.py` (was `THRESHOLD_347_EUR: Decimal`)

Updated callers:
- `_row_models.py` now imports `M347_THRESHOLD_EUR` from `...core.external_constants`
- `_counterpart.py` now imports `M347_THRESHOLD_EUR` from `aeat.core.external_constants`
  and uses it in `declarable_counterparty_nifs_347`; removed `THRESHOLD_347_EUR` from `__all__`
- `domain/modelos/__init__.py` re-exports via `_row_models` chain (unchanged)
- `entrypoints/cli/_modelo.py` imports via `domain.modelos` (unchanged)
- `test_counterpart.py` updated to import `M347_THRESHOLD_EUR` from core
- Regression tests added to `test_external_constants.py`:
  value assertion, isinstance guard, module import identity check,
  anti-tautology AST scan for bare `Decimal("3005.06")` in `_counterpart.py`

## Verification gate

`pytest src/aeat/core/test_external_constants.py src/aeat/application/aggregation/test_counterpart.py src/aeat/domain/modelos/test_row_models.py -q`
— 126 passed, 0 failed.

## Commit

`318c08101` — const(core): centralise M347_THRESHOLD_EUR to external_constants (MERGE-001)
