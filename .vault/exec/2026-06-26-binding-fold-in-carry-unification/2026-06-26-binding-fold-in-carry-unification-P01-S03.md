---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-07-17'
step_id: 'S03'
related:
  - "[[2026-06-26-binding-fold-in-carry-unification-plan]]"
---

# vaultspec-standard-executor: enforce the typed relation op at registry-build via the section validator, rejecting an unknown op at build not resolve time

## Scope

- `src/aeat/domain/calculations/registry/_validate_relation_sources.py`

## Description

- Enforce the typed relation op at registry-build via the strict `RelationAggregation.op` field: an unknown op is rejected when the `RelationDefinition` is constructed, earlier than the section validator, at parity with the binding op gate.
- Remove the now-redundant inline op-check from the relation section validator in `_validate_relation_sources.py`.

## Outcome

- Landed in the single atomic P01 commit `4b3311a02`. The build-time rejection is the strongest gate (construction-time), matching how `BindingAggregation` enforces binding ops. The committed-registry build validates clean.

## Notes

- The section-validator op-check became unreachable once the field is strictly typed (a relation that constructed successfully already carries a valid op), so it was deleted rather than left as dead defence-in-depth.
