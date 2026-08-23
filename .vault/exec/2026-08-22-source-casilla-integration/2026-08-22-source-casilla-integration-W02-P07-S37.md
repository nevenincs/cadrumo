---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:19b0e5dbf5b5fab982ddd9219bc6fc48fde63e2a87fba3dbb39370634bd202e3'
step_id: 'S37'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# define and validate the typed inventory selector contract

## Scope

- `src/cadrumo/domain/calculations/registry/_inventory_bindings.py`

## Description

- Define one strict frozen selector for the approved 2025 Modelo 100 inventory projection.
- Couple complete acquisition cost and both non-negative stock-variation directions to their exact registry destinations.
- Expose one accumulating family validator for later registry enrollment without enrolling or resolving the source.
- Prove the selector refuses stale, signed, cross-year, cross-modelo, wrong-grain, extra-key, and readiness-claim shapes.

## Outcome

The inventory binding family now has a closed typed authoring vocabulary for the taxpayer/year/activity projection. It can name only complete acquisition cost into 0181, positive closing-minus-opening into 0177, or positive opening-minus-closing into 0182. Source completeness and readiness remain resolver-owned future work.

## Notes

Formal review passed with no findings. Nineteen focused selector tests, Ruff, and `ty` pass. Registry dispatch, bindings, source resolution, and readiness were deliberately not changed in this step.

