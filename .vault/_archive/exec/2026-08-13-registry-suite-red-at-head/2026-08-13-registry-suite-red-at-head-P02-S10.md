---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:59722ef23406446f8e6abda74d8a41258076464ec37ee3b0dd1056c5dc6b1103'
step_id: 'S10'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---

# Add one regression driving a real 2024 2T negative settlement credit into the 3T return and asserting the resulting compensacion figure

## Scope

- `src/cadrumo/application/calculations/tests/`

## Description

- Calculate and persist a real 2024 2T negative M303 settlement through the
  encrypted observation repository with its law-selected early revision stamp.
- Resolve its previous-quarter relation into the 2024 3T late revision and
  assert source identity, binding materialization, and casilla 110.
- Persist the same source with the wrong late revision stamp and prove the live
  carry gate refuses it.

## Outcome

The early 2T revision calculates `21 - 63 = -42` and exposes EUR 42 available
compensation. The late 3T revision consumes exactly that 2024/2T source and
materializes EUR 42 into its prior-period compensation binding and casilla 110.
A source falsely stamped with the late revision produces no relation value.

## Notes

- Expected arithmetic and carry direction are grounded in LIVA article 99 and
  the official early/late M303 design authorities, not read back from the engine.
- Owned module: 5 passed. Adjacent relation-consistency and mid-year-design
  tests: 5 passed, with eight pre-existing OpenPyXL warnings.
- Ruff, format, and scoped diff checks passed.
- Independent review found no blocking issue, mock, duplicated resolver, or
  tautological oracle.
- Implementation commit: `c2408f0e81`.
