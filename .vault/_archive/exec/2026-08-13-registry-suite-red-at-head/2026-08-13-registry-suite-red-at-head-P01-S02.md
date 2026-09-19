---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:30dcc34997712dcff319d4480845cd110d14adea78c6bddf21f45c80a2fd17f2'
step_id: 'S02'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---
# Resolve offset-derived periods across the union of split source revisions

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_relation_consistency.py`

## Description

The relation consistency gate no longer requires every candidate revision to
contain every relation period. It consumes the production coordinate-coverage
result, then checks each covered revision only for the periods assigned to it
and for the referenced source casilla. This makes the 2024 Modelo 303 split
load-bearing: first-half and second-half revisions jointly cover the relation
without either pretending to own all four quarters.

## Outcome

The owning module passes two tests. Ruff and BasedPyright are clean, and
`git diff --check` reports no defect. The fix delegates period/year semantics to
production and retains an independent assertion over the source output, so the
test does not mirror registry business logic.

## Notes

S01 and S02 land together because the canonical coordinate resolver supplies
both the offset-year result and its unique split-revision owner. There is no
honest intermediate contract between those two facts.
