---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S46'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W04.P08.S46 Resume Facade Routing

Scope: route resume target resolution through centralized modelo addressing before workflow-run lookup.

## Description

- Introduce `resolve_modelo_workflow_resume_target` in the workflow application layer.
- Resolve visible filing targets through `ModeloVisibleFilingTarget` and the public modelo work-addressing facade.
- Resolve exact work-unit ids through `ModeloExactWorkUnitTarget` and the public modelo work-addressing facade.
- Resolve calculation revision selectors through the public modelo revision-pick facade before selecting a workflow run.
- Refuse incomplete, contradictory, or ambiguous resume targets with translated workflow errors.

## Outcome

Workflow resume target selection now follows the same natural-key-to-exact-target path as the rest of modelo work addressing. The CLI consumes the facade and no longer reimplements target resolution.

## Notes

Raw ids remain advanced exact-addressing escape hatches. Visible target ambiguity refuses rather than guessing.
