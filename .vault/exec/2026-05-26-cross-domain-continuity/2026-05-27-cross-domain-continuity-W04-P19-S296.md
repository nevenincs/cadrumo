---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S296
plan: "[[2026-05-26-cross-domain-continuity-plan]]"
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W04.P19.S296 — R8-M200-1 DP200014:00562 TOML reclassification

## What was done

Fixed the TOML misclassification of casilla `DP200014:00562` (cuota íntegra,
Liquidación III) in the Modelo 200 `2024-y-siguientes` revision.

Before this fix the TOML declared `input_kind = "manual"` and `required = true`
even though formula `modelo-200-cuota-integra` computes the value from the
post-nivelación base imponible. This caused `verify_modelo_revision` to demand
the cuota íntegra as a user-supplied input, making every S.A. (and SL, etc.)
M200 filing refuse VERIFICADO_COMPLETO with a spurious MISSING_REQUIRED_CASILLA
finding.

### TOML change

`src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/liquidacion-00562-cuota-integra.toml`:

- `required = true` → `required = false`
- `input_kind = "manual"` → `input_kind = "computed"`
- Added: `formula = "modelo-200-cuota-integra"` (required by schema validator)

### Regression tests added

Three new invariants appended to
`src/aeat/domain/calculations/registry/test_modelo_200_temporal_coverage.py`:

1. `test_cuota_integra_casilla_is_classified_computed_not_manual` — asserts
   the snapshot carries `input_kind = "computed"` and `required = False` for
   `DP200014:00562`; fails against the pre-fix TOML.

2. `test_cuota_integra_is_emitted_by_engine_without_user_input` — asserts
   `calculate_registry_snapshot` emits `DP200014:00562` in `result.values`
   without the caller supplying it in `inputs`; pins the S.A. (gran empresa,
   LIS Art. 29.1 general rate 25 %) oracle value of 50.000 EUR on a 200.000 EUR
   base.

3. `test_cuota_integra_antitautology_manual_casilla_still_required` — asserts
   casilla `00501` (resultado cuenta pérdidas y ganancias, an operator-supplied
   figure) still carries `input_kind = "manual"` and `required = True` in the
   same snapshot; proves the classification machinery discriminates correctly
   and that invariants 1-2 are not vacuous.

### Pre-existing unused imports cleaned

Removed unused `RegistryValidationError` import and `validate_bracket_table_temporal_coverage`
import from the modified test file (pre-existing ruff F401 warnings that became
mandatory to fix when the file was touched). Also fixed two pre-existing RUF002
EN DASH characters in docstrings.

## Gate results

- `pytest test_modelo_200_temporal_coverage.py`: 7 passed
- `pytest test_modelo_200_cuota_integra_lanes.py test_modelo_200_registry.py`: 18 passed
- `ruff check` + `ruff format --check`: clean
