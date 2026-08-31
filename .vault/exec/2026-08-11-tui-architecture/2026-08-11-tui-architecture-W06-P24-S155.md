---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:c315dc89643b341096b00b0f90b88c92b5e73fc6da82df1fc988153cff430c73'
step_id: 'S155'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Enroll modelo.work.amend through the existing amend_modelo_revision authority as the sole C4 amendment mutation, with baseline evidence, amendment-kind REVIEW, atomic catalogue/event effects, safe result receipt, typed Workspace refresh target, and an explicit amend-wizard denominator disposition

## Scope

- `src/cadrumo/application/modelo/_operation_definitions.py and src/cadrumo/application/modelo/_amendment_actions.py`

## Changes

- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `M` `src/cadrumo/application/modelo/tests/test_work_rename_operation.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_work_rename_operation.py -n0` -> `pass` (31)

## Notes

The request names the filed record an amendment corrects rather than a work
unit: the baseline supplies the full casilla map and the overrides replace only
what changed. A reason is required, because declaring a previously filed figure
wrong is a statement to the tax authority and a correction with none is not
something an operator should be able to record.

Override values cross as exact decimal STRINGS. The public operation schema
contract requires validation and serialization to be one shape, and a bare
Decimal is not: it accepts number-or-string and emits string. Carrying the
digits satisfies the contract and removes any float coercion on the way; the
override exposes `as_decimal()` for the authority call.

Which amendment kinds a modelo admits, and whether the baseline is
AEAT-attested, stay the authority's decisions. A gate asserts the executor
names neither, alongside the same no-policy-duplication proof the other
enrolments carry.
