---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S73'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P08.S73 AEAT Sede Declarations Decomposition

Scope: `src/aeat/adapters/outbound/aeat/sede/_declarations.py src/aeat/adapters/outbound/aeat/sede/*.py`.

## Description

- Extract the `Declaracion` register row boundary model from `_declarations.py` into `_declarations_schema.py`.
- Extract ZK listbox row parsing from `_declarations.py` into `_declarations_listbox.py`.
- Extract filed-declaration observation, submitted-file/PDF casilla interpretation, registry snapshot policy lookup, and registry binding resolvers from `_declarations.py` into `_declarations_observations.py`.
- Keep `_declarations.py` importing and re-exporting `Declaracion` and existing private test hooks for existing adapter callers.
- Preserve the sede package-level facade export for `Declaracion`.

## Outcome

The declarations workflow module no longer owns the `Declaracion` pydantic boundary model, listbox parsing, or filed-observation registry interpretation helpers directly. `_declarations.py` now focuses on authenticated read-only browser orchestration and is 1243 lines, below the module-size target, while the public sede facade remains stable.

## Notes

No production consumer-facing import path changed. Existing private test hooks remain available from `_declarations.py`. No behavior skips, fakes, mocks, monkeypatches, or xfails were introduced.
