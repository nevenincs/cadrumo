---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:b8e180e694455c4b9f1ad3b85cdc951918a54fd8ecbe9bdb401b566070b5523f'
step_id: 'S04'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---

# Inventory deterministic producers, formula targets, and casilla declarations across the validated registry

## Scope

- `src/cadrumo/domain/calculations/registry/_schema.py`

## Description

- Added the lossless revision-local producer inventory.
- Indexed formula targets, formula declarations, computed casillas, producer kinds, and producer reasons without last-write-wins collapse.
- Classified formula, manual, upstream, relation, and informational paths from existing typed declarations.
- Added real-registry inventory coverage.

## Outcome

The inventory measured 73 modelos, 90 revisions, 15,774 casillas, 1,256 formulas, and 1,256 computed casillas with no live inventory mismatch in the worker-era run. Intentional manual, upstream, relation, and informational paths remain visible rather than being treated as formula gaps.

Focused inventory and broader registry checks passed during the worker run. Current validator replay is blocked before the registry assertions by the unrelated invalid profile schema documented in the tranche review audit.

## Notes

No formula, profile, relation, or model data was changed. Full repository testing and current whole-registry validation remain unverified.
