---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:bf507681bab78b515014c06c5ccd4c7b6561ccefcf1895fb23a59985c65ff126'
step_id: 'S150'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Enroll modelo.work.rename through the existing rename_work_unit single writer with exact approval and capability rules, declared atomic write set, safe effect and result receipt, and typed Workspace refresh target without recreating lifecycle policy

## Scope

- `src/cadrumo/application/modelo/_operation_definitions.py and src/cadrumo/application/modelo/_work_lifecycle.py`

## Changes

- `A` `src/cadrumo/application/modelo/operation_definitions.py`
- `A` `src/cadrumo/application/modelo/tests/test_work_rename_operation.py`
- `M` `docs/api/cadrumo.application.modelo.rst`
- `A` `docs/api/cadrumo.application.modelo.operation_definitions.rst`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_work_rename_operation.py -n0` -> `pass`

## Notes

The Step row names a private `_operation_definitions.py`. It is public here:
every existing enrolment exemplar is public, and a definition must be
importable by a composition root outside this package. Recorded as a
plan-vs-code reconciliation rather than followed blindly.

The enrolment recreates no lifecycle policy. `rename_work_unit` already owns
the rules and the atomic write set - catalogue and lifecycle event co-commit
inside it - so the executor only delegates. A gate asserts that and was proved
to bite by planting a discard check in the executor.

The declared capabilities follow from the writer: RECORDED durability,
INTERRUPT reconciliation (a rename cannot resume after owner loss), a
credential-free journalable request, and a public result projection that
carries no lifecycle state a consumer could depend on.

### Carry-forward: the typed Workspace refresh target was not built

This Step's own title claims a "typed Workspace refresh target." It was not
delivered: no `ModeloWorkspaceRefreshTargetV1` type, adapter, or reference
exists anywhere in `src/` after this Step's commit, and
`OperationPublicDefinitionRegistrationV1.workspace_refresh_adapter` is left
unset on the rename registration, exactly as on every other enrolled modelo
lifecycle operation. The rest of this record's claims hold - lifecycle
delegation, capability declaration, and the discard-planting gate proof are
real and verified - so the Step's checkbox stays closed rather than reverted.
The missing mechanism is now tracked as its own Step,
`W05.P23.S306`, discovered and carved out while building `S144`.
