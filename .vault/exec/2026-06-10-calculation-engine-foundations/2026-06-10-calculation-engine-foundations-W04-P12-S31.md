---
tags:
  - '#exec'
  - '#calculation-engine-foundations'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S31'
related:
  - '[[2026-06-10-calculation-engine-foundations-plan]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
  - '[[2026-06-10-period-revision-resolution-adr]]'
---

# W04.P12.S31 Unresolved Relation Robustness

Scope: implement the non-blocking unresolved relation path for formula-consumed cross-modelo fold-ins.

## Description

- Add an unresolved relation channel to the source mesh contract and merge path.
- Emit relation-prefill diagnostics for formula-consumed missing relations, including source modelo, year, periods, and output.
- Propagate source-classified unresolved relation operands through the registry formula runtime without zero contribution.
- Omit downstream computed casillas that depend on unresolved computed casillas.
- Preserve hard `RegistryValidationError` behavior for relation operands missing outside the explicit unresolved source channel.
- Preserve first-ejercicio M200 bound self-carry zero behavior for relation-prefill bindings that are not formula operands.
- Add a live M200 regression proving missing same-year M202 pagos produce an advisory and leave `DP200014B:00611` unresolved.

## Outcome

`S31` is implemented. The previous period-refactor blocker is no longer active for this item: the live calculate path now carries enough typed period context for the relation resolver to name the missing source periods and for the engine to distinguish source absence from registry wiring bugs.

## Notes

No mocks, skips, xfails, or monkeypatches were introduced. The regression uses the existing encrypted repository-backed live M200 calculation path.
