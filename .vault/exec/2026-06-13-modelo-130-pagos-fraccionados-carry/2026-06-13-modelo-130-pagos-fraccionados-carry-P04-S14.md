---
tags:
  - '#exec'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S14'
related:
  - "[[2026-06-13-modelo-130-pagos-fraccionados-carry-plan]]"
---




# add the coverage-validator-treats-empty-span-as-satisfied case: assert previous_filing_observation_requirements emits no required observation for an empty span and the cross-period gate returns clean for a genuine first filer

## Scope

- `src/aeat/domain/calculations/registry/tests/test_validate_previous_filing_sources.py`

## Description

- Added `test_validate_previous_filing_sources.py` proving `previous_filing_observation_requirements` emits no casilla-05 requirement for an empty span (1T) and exactly the expanding prior-quarter set at 2T/3T/4T.
- Added the application-layer first-filer clean-state case (in `test_modelo_130_casilla_05_carry.py`) proving the cross-period gate returns clean for a genuine first filer.

## Outcome

The empty span is satisfied (no required observation) and a first filer is clean. Landed in commit `53de169cb`.

## Notes

The 1T requirement bundles the casilla-15 saldo casilla alongside 07/16 (shared period key), so the assertion is a subset check on 07/16 presence rather than exact equality.
