---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:483fa076fa49aa0393b3d6b8d9b4d3b96d0deb7dcea755faebaa3ea0ba61cee6'
step_id: 'S09'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Canonicalize the binding-to-casilla reverse join

## Scope

- `src/cadrumo/domain/calculations/registry/_bindings.py`
- `src/cadrumo/domain/calculations/registry/_rate_box_partition.py`
- The registry package facade and direct reverse-join/rate-box tests.

## Description

- Define `casillas_by_binding` as the exact reverse projection of `bound_casilla_binding_ids`.
- Export the canonical function through the registry facade and delete the private rate-box mapper.
- Route both formed and unscreened rate-box derivations through the canonical reverse join.
- Preserve alternate bindings, exclude non-BOUND declarations, and retain the stronger `CasillaDefinition` construction refusals.
- Reconcile direct tests with the current schema boundary without constructing invalid models.

## Outcome

The repository has one production binding-to-casilla reverse join. The public facade resolves to the same function object, both rate-box paths consume it, the retired private mapper is absent, and the separately planned S10 application mapper remains the only visible noncanonical consumer. Twenty focused tests passed; Ruff, focused BasedPyright, structural identity checks, prohibited-test scans, and scoped diff checks are green. Formal review found no code or test defect.

## Notes

Delivery integrity is recorded explicitly because shared-tree commits absorbed this Step into broader changes. Production implementation, facade export, rate-box retarget, and original tests landed inside `c0fbbb0456`; the stronger-schema prose/test reconciliation landed inside unrelated commit `174f5acaf4`. This violates the plan's one-Step-one-atomic-commit convention and cannot be repaired without rewriting shared history, which is forbidden. This execution record is the formal carry-forward: it names both actual commits, preserves the verified current state, and requires subsequent steps to use ownership-verified path-scoped delivery. No compatibility surface or cosmetic replacement commit was created.
