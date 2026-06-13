---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S65'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P07.S65 Registry Schema Decomposition

Scope: `src/aeat/domain/calculations/registry/_schema.py`, `src/aeat/domain/calculations/registry/*.py`.

## Description

- Split scalar and annotated schema boundary types into `_schema_scalars.py`.
- Split shared schema base aliases and `RegistryModel` into `_schema_base.py`.
- Split formula, bracket, convenio, and parameter schema models into `_schema_formula.py`.
- Split casilla, relation, algorithm, export, record, and completeness schema models into `_schema_surfaces.py`.
- Preserved `_schema.py` as the historical import surface through explicit compatibility aliases and imports.
- Preserved registry package facade exports for public consumers.

## Outcome

`_schema.py` reduced to 1219 lines. New schema-family modules are all below the 1250-line objective.

## Notes

The worktree already contained `_schema_input_kind.py` and `_schema_rounding.py`; this step preserved those prior extractions and repaired the public rounding-code facade compatibility.
