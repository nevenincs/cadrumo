---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
step_id: 'S65'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P07.S65 Registry Schema Decomposition

Scope: `src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/*.py`.

## Description

- Extract the casilla input-kind schema axis from `_schema.py` into `_schema_input_kind.py`.
- Extract the formula rounding-code schema axis from `_schema.py` into `_schema_rounding.py`.
- Keep `_schema.py` re-exporting `InputKind`, `InputKindValue`, and `RegistryRoundingCode` for existing registry imports and the package facade.
- Update `FormulaDefinition.rounding` to use the imported rounding-code annotated value alias.

## Outcome

The registry schema monolith no longer owns the input-kind or rounding-code coercion implementations directly. Those typed axes now live in focused private modules while the public registry facade remains unchanged.

## Notes

No consumer-facing import path changed. No behavior skips, fakes, mocks, monkeypatches, or xfails were introduced.
