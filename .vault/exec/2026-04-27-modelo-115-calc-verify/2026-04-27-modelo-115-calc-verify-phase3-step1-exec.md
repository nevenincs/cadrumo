---
tags:
  - '#exec'
  - '#modelo-115-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-115-calc-verify-plan]]"
  - "[[2026-04-27-modelo-115-calc-verify-adr]]"
---

# Step record — integration parametrisation + fleet-list updates

Plan reference:
`2026-04-27-modelo-115-calc-verify-plan` §3.1.

## Files changed

- `tests/integration/test_kent_workflows.py` — added
  `test_per_year_happy_path_verified` parametrised case to
  `TestKentImportsModelo115Declaracion`, mirroring the M130
  pattern (lines 224..256 of the M130 class). Parametrised over
  `["2024", "2025", "2026"]`. Asserts on stable substrings only:
  `Extraction status: COMPLETE`, `Verification status: VERIFIED`,
  and `f"Modelo 115 {ejercicio}Q1"`.
- `src/aeat/domain/formulas/test_smoke.py` — added `modelo_115.2026`
  to the fleet ID set asserted by
  `test_registry_has_shipped_rulesets`.
- `src/aeat/domain/formulas/test_registry.py` — added `modelo_115.2026`
  to the sorted fleet list asserted by
  `test_registry_ships_modelo_130_and_303_rulesets`.
- `src/aeat/domain/formulas/test_cli.py` — added `modelo_115.2026` to
  the sorted fleet list asserted by `test_list_subcommand`.

## Verification

- `uv run pytest tests/integration/test_kent_workflows.py::TestKentImportsModelo115Declaracion`
  → 7 passed (the existing 4 cases + the new 3-parameter
  parametrisation).
- `uv run pytest src/aeat/domain/formulas/test_cli.py::test_list_subcommand
  src/aeat/domain/formulas/test_registry.py::test_registry_ships_modelo_130_and_303_rulesets
  src/aeat/domain/formulas/test_smoke.py::test_registry_has_shipped_rulesets`
  → 3 passed.

## Notes

The M115 integration class already shipped four cases under
`#340` (English / Spanish / partial / discrepancy classifier).
The per-year case is additive — the existing four cases are
preserved verbatim per ADR §D8.
