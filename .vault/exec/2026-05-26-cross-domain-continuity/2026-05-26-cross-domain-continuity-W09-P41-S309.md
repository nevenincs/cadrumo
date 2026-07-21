---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-07'
modified: '2026-07-17'
step_id: 'S309'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R8-NURIA-MODERATE M131 módulos manual entry path

## Scope

- `today binding source is ledger only`
- `add CLI path for direct module-data entry on M131 for clients without integrated bookkeeping`
- `supplements W05.P22 income aggregation work which only covers EDS`
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Run required vault grounding:
  `uvx vaultspec-rag search "S309 M131 modulos manual entry direct module-data entry CLI without bookkeeping" --type vault --doc-type plan,audit,exec --feature cross-domain-continuity`.
- Run required code grounding:
  `uvx vaultspec-rag search "M131 modulos manual entry CLI casilla modulos epigrafe unidades calculate" --type code`.
- Confirm the existing generic `modelo work calculate --casilla` path already routes text casillas through the text input channel and decimal module-unit casillas through the numeric input channel.
- Add one focused real CLI integration test for an objective-estimation M131/2026 work unit with no ledger observations.
- Keep filed casilla `01` separate from the internal módulos reference computation: the test supplies `01` manually, asserts it remains persisted, and separately asserts `modulos-rendimiento-neto-actividad` is non-zero for a tabled epígrafe.

## Outcome

- No production change was needed. The current CLI already accepts direct manual module-data entry through canonical `--casilla` ids:
  `modulos-epigrafe`, `modulos-1-unidades`, `modulos-1-unidades-anterior`, `modulos-2-unidades` through `modulos-7-unidades`, and `modulos-minoracion-inversion`.
- The new regression proves a client without integrated bookkeeping can create and calculate M131 2026 work with direct module inputs plus `modelo-131-2026-resultados-negativos-anteriores=0`.
- The saved revision carries the manual module inputs in `input_values_by_casilla_id`, while `casilla_values["modulos-rendimiento-neto-actividad"]` is a non-zero advisory/reference output for the tabled `721.2` epígrafe.
- The test intentionally does not claim the computed módulos reference silently replaces filed casilla `01`; it asserts the manual filed value remains distinct.

Validation:

- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py -m integration -k "m131 and modulos"` passed, 1 test.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py` passed.
