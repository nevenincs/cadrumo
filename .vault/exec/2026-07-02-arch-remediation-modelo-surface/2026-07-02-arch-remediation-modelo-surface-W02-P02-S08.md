---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S08'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Delete the _M100_IMPUTATION_YEAR_DAYS constant from the generic formula runtime and read the value from the compiled snapshot instead

## Scope

- `src/aeat/domain/calculations/registry/_formula_runtime.py`

## Description

- Delete the generic `_M100_IMPUTATION_YEAR_DAYS` constant from the formula runtime.
- Extend the M100 Art. 85 formula op contract to require a registry-authored imputation-year-days parameter.
- Read the parameter from the compiled snapshot and validate the supplied imputation days against that declared maximum.
- Add the year-days parameter operand to the 2024 and 2025 M100 Art. 85 formula declarations.

## Outcome

- Direct full-authority M100 calculations for 2024 and 2025 still computed casilla `0089` as `448.80`.
- The calculation trace for each year now includes `renta-<year>-imputacion-inmobiliaria-year-days` as a formula operand.
- Focused ruff check passed for the edited runtime file.

## Notes

- Verification log: `_scratch-codex/w2_s08_m100_direct_calc.log`.
- Ruff log: `_scratch-codex/w2_s08_ruff.log`.
