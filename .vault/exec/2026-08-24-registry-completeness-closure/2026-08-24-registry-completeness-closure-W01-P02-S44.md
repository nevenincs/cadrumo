---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:49559cc62d53543c3217ee46064cf4717f694f5052b9cc062c5e6201a455b9ee'
step_id: 'S44'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Encode branch-specific TemporalRevisionCoverage refusal invariants and add construction and mutation-bite tests.

## Scope

- `src/cadrumo/application/registry/`

## Description

- Encode each temporal-refusal code's branch-specific evidence state in `TemporalRevisionCoverage`.
- Prove every composer-shaped refusal can be constructed directly and impossible branch evidence is refused at construction.
- Revalidate deliberately mutated frozen rows to prove public deserialisation cannot admit contradictory branch evidence.
- Run path-scoped lint and focused temporal-coverage tests.

## Outcome

Temporal closure rows now preserve the exact boundary reached: a law-selection refusal carries no selected revision; selection and snapshot mismatches retain a conflicting revision; undeclared-grade refusals retain the registered selected revision but no grade; and declared-grade snapshot refusals retain both the registered selection and its declared grade. The public model now refuses contradictory direct inputs and revalidated mutation payloads rather than allowing a report to claim evidence that was never reached.

## Notes

Focused lint passed. `pytest -n 0 -q src/cadrumo/application/registry/tests/test_temporal_coverage.py` passed: 26 tests in 35.86 seconds. No source-connectivity or facade files were changed, preserving the concurrent S08 ownership boundary.
