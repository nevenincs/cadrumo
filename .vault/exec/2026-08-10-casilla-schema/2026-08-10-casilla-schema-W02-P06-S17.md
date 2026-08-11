---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:e9e7944929b3fc9860313be42d39598a6b141f95b96ded3bfa91f7ce086ec46b'
step_id: 'S17'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Project cross-period blockers onto operator action classes

## Scope

- `src/cadrumo/application/calculations/_cross_period_models.py`
- `src/cadrumo/application/calculations/__init__.py`
- `src/cadrumo/application/calculations/tests/test_cross_period_blocker_action_projection.py`

## Description

- Add the total `OPERATOR_ACTION_BY_CROSS_PERIOD_CLEAN_STATE_BLOCKER` mapping beside the native 21-member blocker enum.
- Map prior-filing, evidence, verification, divergence, identity, group-membership, and revision-stamp defects onto the accepted `OperatorActionAxis` classes without replacing the native blocker code.
- Refuse module import if any current or future blocker lacks a projection, and expose the exact mapping through the application-calculations facade.

## Outcome

- All 21 blockers map: six filing, six evidence, three divergence, three group-membership, and one each verification, identity, and revision mismatch.
- Two focused tests pass; Ruff, format, BasedPyright, facade, totality, and diff gates are green.
- Formal review reports PASS with no findings.

## Notes

- The import-time bite proof removed `REGISTRY_REVISION_DIVERGENCE`; a clean application-calculations import failed naming that unmapped member, then the row was restored in the same session.
- The broader current clean-state module is 22 passed / 8 failed before projection evaluation: seven invalid justificante CSV fixture constructions and one profile fixture missing explicit `iva.m303_regime_composition`. None reads the new mapping; this boundary is not claimed green.
