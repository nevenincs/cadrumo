---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S35'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M303 two-renta compensation-carry enrollment test proving 4T/2025 saldo into 1T/2026 casilla 110 via real registry calculation and relation resolver

## Scope

- `src/aeat/application/calculations/tests/test_modelo_303_compensacion_carry_forward_continuity.py`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2024-y-siguientes/relations/0001-relations.toml`

## Description

- Rebaseline stale-open M303 enrollment-test row against the current test suite.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M303 test and relation registry.
- Update the plan row to the actual M303 compensation-carry enrollment proof.

## Outcome

- `test_modelo_303_compensacion_carry_forward_continuity.py` already proves 4T/2025 saldo carries into 1T/2026 casilla `110` through real registry calculation and the relation resolver.
- The relation `modelo-303-rel-self-compensacion-anteriores` is declared in the M303 registry.
- No product code changed in this step.

## Notes

- This does not claim `MultiYearResolver` or prorrata art.105 coverage.
