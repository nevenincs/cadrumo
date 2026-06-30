---
tags:
  - '#exec'
  - '#eoy-final-calculation'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S05'
related:
  - "[[2026-06-22-eoy-final-calculation-plan]]"
---

# Extend the 0004-domestic-base M303 ledger base aggregation to every supported 303 revision so base casilla 03/07/28 never populate cuota without base (F3)

## Scope

- `src/aeat/_data/registry/aeat/modelos/303`

## Description

- Ground current implementation with `uvx vaultspec-rag search "Modelo 303 domestic base aggregation casilla 03 07 28 revisions cuota without base" --type code`.
- Enumerate the supported Modelo 303 revisions and inspect current domestic-base binding coverage.
- Run the focused registry regressions proving base and cuota coexist on the current and historical revisions.

## Outcome

- The supported Modelo 303 revisions are `2009-y-siguientes` and `2023-y-siguientes`.
- The current registry carries domestic base aggregation bindings on both supported revisions. The 2023 revision keeps the split `bindings/0004-domestic-base.part-001.toml` records, and the 2009 revision has the inline back-fill for the same base boxes.
- `test_modelo_303_2024_domestic_base_aggregates_from_ledger` proves current-year base casillas aggregate from ledger values while cuota casillas remain populated.
- `test_modelo_303_2009_revision_domestic_base_aggregates_from_ledger` proves the older supported revision also resolves base values for the same ledger inputs, preventing the prior cuota-without-base failure.
- Verification passed in `uv run --no-sync pytest -q --tb=short src/aeat/domain/calculations/registry/tests/test_ledger_iva_aggregation_binding_exports_recargo.py src/aeat/application/calculations/tests/test_modelo_200_202_pagos_fraccionados_fold.py`: 13 passed.

## Notes

- No code change was needed for S05; the current tree already contains the back-fill and focused tests.
