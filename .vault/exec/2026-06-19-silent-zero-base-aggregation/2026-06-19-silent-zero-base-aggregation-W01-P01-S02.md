---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S02'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---




# rerun the completeness-manifest drift gate and M303 registry build and record green after the base casillas join the manifest/construct

## Scope

- `src/aeat/domain/calculations/registry/tests/test_record_design.py`
- `src/aeat/domain/calculations/registry/tests/test_record_design.py`

## Description

Reran the completeness-manifest drift gate and the M303 registry build after the
base casillas joined the manifest and construct.

## Outcome

`test_calculation_completeness_manifests_match_their_calculation_surface` passes for
M303 (the closure-only set 01/04/07/28 is resolved); the full
`test_record_design.py` plus the M303 registry, compensacion-carry, special-case
routing, and filing suites pass (425 passed, 0 failed). The long-standing M303
manifest-drift blocker is closed.

## Notes

The only remaining repository red is the pre-existing `test_tautology_gate` flag on
a committed peer iva-wallet test (hand-summed assertions), which is peer-owned and
outside this feature's surface.
