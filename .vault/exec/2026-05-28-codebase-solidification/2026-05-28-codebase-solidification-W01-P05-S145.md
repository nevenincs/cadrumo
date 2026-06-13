---
step_id: S145
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P05.S145 — canonical `_round_to_cents` in `aeat.domain.fincas._rounding`

## Outcome

Created `src/aeat/domain/fincas/_rounding.py` exporting `_round_to_cents(value:
Decimal) -> Decimal` using `value.quantize(_CENT, rounding=ROUND_HALF_UP)` where
`_CENT = Decimal("0.01")`. Migrated all three call-site modules to import from
the canonical module; deleted the two peer copies in `_amortization_ledger.py`
and `_expense_rollup.py`; removed the local definition and `ROUND_HALF_UP` /
`_CENT` declarations from `_aggregates.py`.

## Files touched

- `src/aeat/domain/fincas/_rounding.py` (created — canonical definition)
- `src/aeat/domain/fincas/_aggregates.py` (local `_round_to_cents` + `_CENT` + `ROUND_HALF_UP` import deleted; `._rounding` import added)
- `src/aeat/domain/fincas/_amortization_ledger.py` (local `_round_to_cents` + `_CENT` + `ROUND_HALF_UP` import deleted; `._rounding` import added)
- `src/aeat/domain/fincas/_expense_rollup.py` (local `_round_to_cents` + `_CENT` + `ROUND_HALF_UP` import deleted; `._rounding` import added)

## Collision check

`git diff` on all four target files returned empty output before first edit — no
peer WIP in scope.

## Test outcome

12/12 passed: `uv run --no-sync pytest src/aeat/domain/fincas/test_rounding.py -xvs`
Import smoke-test (`python -c "from aeat.domain.fincas._rounding import _round_to_cents; ..."`) passed clean.
