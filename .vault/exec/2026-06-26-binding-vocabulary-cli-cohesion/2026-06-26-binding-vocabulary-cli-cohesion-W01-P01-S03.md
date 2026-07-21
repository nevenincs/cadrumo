---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-07-17'
step_id: 'S03'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# Assert BindingPreviewRowPayload (A2) and _BindingRow (A4) are already role-distinct / module-private at HEAD and confirm no bare BindingRow stem collision remains

## Scope

- `rename _BindingRow to _EntradasBindingRow only if a residual stem collision is found in calc_sheets/_layout.py`
- `src/aeat/entrypoints/cli/_modelo_payloads.py`
- `src/aeat/application/storage/calc_sheets/_layout.py`

## Description

- Assert `BindingPreviewRowPayload` (A2) is already role-distinct at HEAD: it carries its own name with no bare `BindingRow` stem and exists at the def in `_modelo_payloads.py`.
- Assert `_BindingRow` (A4) is module-private to `calc_sheets/_layout.py`: all six occurrences (def plus five uses) are confined to that one file with zero cross-module reach.
- Confirm the bare `BindingRow` stem search across `src/` returns no matches after S01 and S02 landed, so no residual stem collision remains.

## Outcome

No-op assert Step, no code change and no commit. A2 and A4 are confirmed genuine no-ops. The optional `_BindingRow` to `_EntradasBindingRow` rename was conditioned on finding a residual stem collision; none exists (the module-private symbol cannot collide outside its file, and the bare-stem grep is empty), so the rename was correctly skipped.

## Notes

None.
