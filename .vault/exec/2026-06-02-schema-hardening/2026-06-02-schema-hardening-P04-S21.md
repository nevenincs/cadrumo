---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S21'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# Assess schema model extraction boundaries and ADR need

## Scope

- `src/aeat/domain/calculations/registry/_schema.py`

## Description

- Audit the current `_schema.py` model families and working-tree diff.
- Identify generic schema-family extraction boundaries.
- Determine whether the planned extraction requires an ADR.
- Record the compatibility and verification constraints for future
  extraction commits.

## Outcome

- Completed as an audit-only slice. `_schema.py` remains unchanged by
  this step because it contains active peer formatting WIP.
- Internal, behavior-preserving decomposition does not require a new ADR
  if `_schema.py` remains a compatibility facade and public re-exports
  stay stable.
- Any schema construction change, modelo-specific schema module, fragment
  inheritance model, or delta-style registry semantics requires a new ADR
  before implementation.
- The recommended first implementation slice is extraction of generic
  scalar/base schema types and validators behind `_schema.py`
  compatibility re-exports.

## Notes

- No production code was edited, so no Python tests were run for this
  audit-only step.
- Vault checks and code-review logging were run before commit.
