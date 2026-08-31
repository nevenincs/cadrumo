---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:fd64e48e2a4b0d56f4bc2ac57872b6064922d14c75bf4bfd64dcc17ce3346c39'
step_id: 'S161'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Adopt the positive-count alias at the twelve domain and application sites restating its bound, leaving the wider non-negative sweep to its own precondition

## Scope

- `src/cadrumo/core/tabular.py`
- `src/cadrumo/domain/`
- `src/cadrumo/application/workflow/run_models.py`

## Changes

- `M` `src/cadrumo/core/tabular.py`
- `M` `src/cadrumo/domain/calculations/registry/m303_orden_projection_models.py`
- `M` `src/cadrumo/domain/calculations/registry/query_reports.py`
- `M` `src/cadrumo/domain/fincas/models.py`
- `M` `src/cadrumo/application/workflow/run_models.py`
- `verify:` `error_count` probed -- 0 refused on the field, 1 and 5 accepted
- `verify:` all five changed modules import cleanly in isolation

## Notes

The count census found 442 integer count fields: 189 bare `int`, 130 spelling
`Field(ge=0)`, 28 defaulted to zero with no bound at all. That whole population
is P08.S51's, and that step gates itself on "once the shared tree is quieter" --
which it is not: a peer is relocating `core/` module by module and four different
modules have gone missing mid-run today. Attempting 189 edits across domain,
application and adapters against that would collide badly, so the wide sweep is
left where its own precondition puts it.

The slice taken instead is the one the local alias exists for. `PositiveCount`
was minted because pydantic's `PositiveInt` is NOT a drop-in at these sites: it
is `Gt(0)` where these are `Ge(1)`, which admits the same integers but
serialises to `exclusiveMinimum: 0` rather than `minimum: 1` on a published
envelope. Six CLI payloads had adopted it; twelve domain and application fields
still spelled `Field(ge=1)` by hand.

Checked rather than assumed on the one that looked wrong: `error_count` at
`ge=1` reads like a defect, since a count of errors should surely allow zero. It
is on `WorkflowValidationFailedDetails` -- a record that exists only when
validation FAILED, so zero errors would be incoherent. Correct as it stands, and
`PositiveCount` says so more clearly than the raw bound did.
