---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S48'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W05.P13.S48 Centralized Addressing Migration

Scope: rewire adjacent modelo CLI consumers so work-unit and calculation-revision addressing policy is owned by the application layer.

## Description

- Add application facades for operator target addressing: `normalize_modelo_work_period`, `modelo_work_address_from_operator_target`, `resolve_modelo_work_unit_for_operator_target`, and `resolve_modelo_revision_for_operator_target`.
- Export those facades from the top-level `aeat.application.modelo` package.
- Change legacy `_modelo.py` compatibility shims to validate CLI token shape, then delegate work-unit and revision selection to the application facades.
- Change `modelo export` to consume `resolve_modelo_revision_for_operator_target` directly instead of receiving a private resolver callback from `_modelo.py`.
- Preserve resume routing through the workflow application facade `resolve_modelo_workflow_resume_target`.

## Outcome

Calculate, lifecycle, verify, file, revision, history, compare, reconcile, export, and resume paths now resolve model-period work and revision targets through centralized application facades rather than rebuilding selector policy in CLI command bodies.

## Notes

The legacy root still contains compatibility shims while decomposition continues, but those shims now delegate selection policy to backend application services.
