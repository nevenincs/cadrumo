---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S18'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Add an AST gate that inventories per-modelo tokens matching Modelo.M-star and underscore-M-digits patterns across a named list of generic domain and application modules

## Scope

- `src/aeat/tests/test_generic_module_modelo_carveouts.py`

## Description

- Add `test_generic_module_modelo_carveouts.py`: an AST gate inventorying `Modelo.M###` enum attrs and `_M###_*` module constants across a named list of generic application modules.

## Outcome

The gate walks each named module's AST and collects distinct per-modelo tokens. Commit `892faa383`.

## Notes
