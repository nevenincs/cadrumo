---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-07'
modified: '2026-07-17'
step_id: 'S302'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R8-ROSA-F add regime incompatibility warnings

## Scope

- `today a profile with irpf.estimation_regime=objetiva can still create M130 (estimacion directa) without any warning and M303 calculated under general regime without flagging the profile declares SIMPLIFICADO`
- `surface a refused/warning when modelo and profile regime conflict`
- `src/aeat/application/overview/`

## Description

- Ground S302 with `uvx vaultspec-rag search "S302 regime incompatibility warnings M130 objetiva M303 SIMPLIFICADO" --type code`.
- Ground S302/S299 with `uvx vaultspec-rag search "S302 S299 regime incompatibility warnings simplificado" --type vault`.
- Verify the M130 half is already satisfied by the registry applicability and overview calendar tests: objective-estimation profiles resolve M130 as `NOT_APPLICABLE`, M131 as `APPLICABLE`, and overview suppresses M130 rows.
- Preserve the S299 boundary: SIMPLIFICADO M303 ledger-preflight bypass exists, but full casilla 47-58 forfait routing remains corpus-blocked behind the annual Orden de módulos tariff corpus.
- Add an overview calendar warning for active M303 rows when the profile declares `iva_regime=SIMPLIFICADO`, using code `iva.regime.m303_simplificado_forfait_unavailable`.
- Add focused real-behaviour overview tests that build the real calendar for SIMPLIFICADO and GENERAL profiles and assert the warning is present only for SIMPLIFICADO M303.

## Outcome

S302 is honestly handled at the warning/refusal surface requested for `src/aeat/application/overview/`.

The M130 objetiva half was not changed because it was already fixed before this step:
`derive_modelo_applicability` routes objective-estimation economic activity to M131 and marks M130 `NOT_APPLICABLE`; the existing overview calendar test proves M130 does not appear as a confident due row for an objetiva autónomo.

The M303 SIMPLIFICADO half now has an explicit overview warning. This does not claim that the local calculation engine implements the full régimen-simplificado forfait route. It prevents the overview surface from silently presenting M303 for a SIMPLIFICADO profile as if the general-regime calculation path were complete.

Changed files:

- `src/aeat/application/overview/_calendar_warnings.py`
- `src/aeat/application/overview/_calendar.py`
- `src/aeat/application/overview/tests/test_calendar_regime_warnings.py`

Verification run:

- `uv run pytest src/aeat/application/overview/tests/test_calendar_regime_warnings.py src/aeat/application/overview/tests/test_applicability.py::test_pago_fraccionado_regime_matrix_routes_modelos_130_and_131 -q` — passed, 3 tests.
- `uv run ruff check src/aeat/application/overview/_calendar.py src/aeat/application/overview/_calendar_warnings.py src/aeat/application/overview/tests/test_calendar_regime_warnings.py` — passed.

## Notes

Broader overview/registry-backed tests are currently blocked by unrelated shared worktree registry WIP in Modelo 100:

- Initial focused run including `test_calendar.py`, `test_calendar_taxpayer_model.py`, and `test_applicability.py` failed during collection/loading because `src/aeat/_data/registry/aeat/modelos/100` carried an invalid relation `dependency_role='direct_annual_settlement'`.
- A later selected run against `test_calendar_taxpayer_model.py::test_calendar_excludes_non_applicable_modelos` still failed before test execution because Modelo 100 dependency classification `renta-2024-dep-131` lacked relation legal/source refs.

Residual edge: full M303 régimen-simplificado casilla 47-58 computation remains intentionally out of scope and corpus-blocked, matching the S299 execution record. This step adds an honest warning surface only.
