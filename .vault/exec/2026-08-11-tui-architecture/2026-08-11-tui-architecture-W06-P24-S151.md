---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:84a4dfa79ce595d15a41650f6783e4f274e2c50fdf4041739fb0d1f0f4831782'
step_id: 'S151'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Enroll modelo.work.discard through the existing discard_work_unit single writer with exact destructive approval, no-effect refusal, declared atomic write set, safe effect receipt, and typed selection refresh target without recreating lifecycle policy

## Scope

- `src/cadrumo/application/modelo/_operation_definitions.py and src/cadrumo/application/modelo/_work_lifecycle.py`

## Changes

- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `M` `src/cadrumo/application/modelo/tests/test_work_rename_operation.py`
- `M` `src/cadrumo/core/errors/registry/_application_part2.py`
- `M` `src/cadrumo/locales/{es,en,ca,hu}/errors.yml`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_work_rename_operation.py -n0` -> `pass` (13)

## Notes

Discard is destructive, so approval binds to a STATE rather than an id: the
request carries the unit the operator actually saw, including the observed
`updated_at`, and an approval whose unit has moved since is refused instead of
discarding something the operator never approved.

The enrolment holds no lifecycle rule. Whether an already-discarded unit may
be discarded again is the writer's decision, and it refuses that itself with
no effect; the approval check only refuses acting on an unapproved state. A
gate asserts the executor names neither the discarded state nor the writer's
refusal, so the two concerns cannot drift into the enrolment.

test_registry_enforcement is red on `ModeloEditScalarIntentKind` from a peer's
uncommitted `_edit_models.py`, not on this work.
