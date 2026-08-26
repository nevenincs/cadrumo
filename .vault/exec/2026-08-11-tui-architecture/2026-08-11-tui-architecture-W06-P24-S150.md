---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:bf09943a835152c05acaa4d6258a94151526780b470bc540b87410d1f2f8c291'
step_id: 'S150'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
