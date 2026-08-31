---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:6062d3cb8aa234165b25cfbc728b56a44752ccf4682fac5deab9187375526c37'
step_id: 'S66'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Derive spinner visibility, enabled controls, close policy, interaction affordance, and terminal copy solely from OperationPublicProjectionV1 and public response-control projections without reclassifying lifecycle truth

## Scope

- `src/cadrumo/entrypoints/tui/operations/projection.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/operations/projection.py`

## Notes

This Step's derivations (spinner visibility, control enablement, close
policy, interaction affordance, terminal copy key) were authored together
with S61's view-model shape in the same file in one pass, since the
derivation logic and the model it populates cannot be split without leaving
an intermediate commit with an unpopulated view model. No further edit was
needed in this Step.
