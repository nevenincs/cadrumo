---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:819d4350f7537dee8415138bc89af3f4bb495f8c76b07eca63e444d23a8f9c42'
step_id: 'S153'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Enroll modelo.work.file through the existing file_modelo_revision authority as local filing and human handoff only, with precondition refusal, exact approval, atomic filing effects, safe result receipt, and typed Workspace refresh target

## Scope

- `src/cadrumo/application/modelo/_operation_definitions.py and src/cadrumo/application/modelo/_filing_actions.py`

## Changes

- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `M` `src/cadrumo/application/modelo/tests/test_work_rename_operation.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_work_rename_operation.py -n0` -> `pass` (23)

## Notes

Live AEAT submission is prohibited, so `handoff_required` is a contract field
fixed true rather than something computed: the operation records a filing
locally and hands the operator the artefacts to submit themselves.

A gate proves the executor reaches no remote surface. It scans the AST rather
than the source text, which mattered: the executor's own docstring says it
never submits, and the first substring version of the check fired on that
sentence - while an actual call spelled through an attribute would have
slipped past it. Proved by planting a submit_declaration call and watching the
row red.

Approval names the revision AND the verification that justified it. A revision
re-verified since approval is a different fact, and filing on the strength of
the older look would record an intent nobody formed. Every other precondition
- verification state, cross-period cleanliness, election legality - refuses in
the filing authority, and a gate asserts the executor names none of them.
