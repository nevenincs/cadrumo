---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:b3164e8822d230f32986276c75423d7c96731518c1e6658d58a3fc82d644ef5a'
step_id: 'S43'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [M | opus-medium] Rule on the casilla-shaped rows that live OUTSIDE the casilla family. Roughly 4,821 of them sit in the completeness manifest across 93 files — more total rows than the casilla family itself carries. The decision's scope is drawn as a FAMILY boundary, but the row shape crosses it, so the materialiser and the minimality screen both need to know whether a manifest row is inherited, restated, or out of scope entirely. Decide it explicitly rather than discovering it during the pilot. Proof: the ruling is stated in the decision record and both the merge and the screen behave as it says on a fixture containing manifest rows.

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `M` `.vault/adr/2026-09-09-registry-edition-authoring-adr.md`

## Notes

Ruling only. The manifest family does not inherit, which scoped the minimality screen to casilla rows and is stated in the ADR.
