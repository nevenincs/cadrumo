---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S67'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# write the M714 >=2-renta E2E test asserting year-over-year wealth-base calculation via real adapters (vaultspec-high-executor)

## Scope

- `src/aeat/application/calculations/test_modelo_714_wealth_continuity.py`

## Description

- Add a two-year Modelo 714 enrollment test for the art.31 joint-limit calculation.
- Persist real local Modelo 100 observations for 2023 and 2024.
- Resolve same-year Modelo 100 relation values from the local observation store, then calculate Modelo 714 through the real registry formula runtime.
- Record both annual calculation results through the enrollment recorder.

## Outcome

- Satisfied by `test_modelo_714_patrimonio_joint_limit_calculation.py`.
- The test proves two distinct renta years use real local observations, relation resolution, registry snapshot calculation, and manifest matching.
- Verified by `uv run --no-sync pytest -q -n 0 src/aeat/application/calculations/tests/test_modelo_714_patrimonio_joint_limit_calculation.py`, which passed 2 tests.

## Notes

- The asserted numbers are derived from the legal formula wiring and scenario inputs. They are not external oracle figures.
