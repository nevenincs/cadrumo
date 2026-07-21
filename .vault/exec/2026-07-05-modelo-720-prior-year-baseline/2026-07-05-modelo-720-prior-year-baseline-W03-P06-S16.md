---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S16'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---
# Enroll the foreign-assets resolver in the live calculate mesh only after row-carrier parity gates pass

## Scope

- `src/aeat/application/modelo/_calculation_actions.py`
- `src/aeat/application/aggregation/_source_mesh.py`
- `src/aeat/application/modelo/tests/test_source_boundary_and_enrollment.py`
- `src/aeat/application/aggregation/tests/test_source_resolver_enrollment.py`
- `src/aeat/domain/calculations/registry/_donativo_bindings.py`
- `.vault/plan/2026-07-05-modelo-720-prior-year-baseline-plan.md`
- `.vault/audit/2026-07-05-modelo-720-prior-year-baseline-audit.md`

## Description

- Remove `foreign_asset` from deferred source-kind governance after the row-carrier parity steps landed.
- Thread optional typed foreign-asset observations through the bucket calculation API into the source mesh.
- Enroll `ForeignAssetsAggregationSourceResolver` in `_resolve_bucket_source_mesh`.
- Update resolver-enrollment, source-kind parity, deferred-advisory, and M720 live calculation tests for the enrolled partition.
- Remove a stale docstring reference that still listed `foreign_asset` among the deferred detail-row families.

## Outcome

- M720 `foreign_asset` bindings are now owned by the live calculate source mesh instead of the deferred advisory set.
- Supplied foreign-asset observations flow through the approved row carrier and persist as structured `row_binding_values`.
- The deferred set now covers only still-unenrolled detail-row source kinds.
- The reflective resolver-enrollment gate includes the foreign-assets resolver, so it cannot drift dormant again.

## Notes

- Gates passed: scoped ruff check; scoped bytecode compilation; focused source-boundary/enrollment pytest with 25 tests; focused foreign-assets/row-replay pytest with 60 tests; source-mesh readiness pytest with 27 tests; feature-index check.
- The repository import-hygiene gate was also run and remains blocked by pre-existing test-only private-import debt outside this step.
- No new binding source kind, resolver convention, validator convention, foreign-asset repository convention, or re-export was introduced.
- The calculation API accepts typed foreign-asset observations explicitly because no durable foreign-asset observation store exists under the approved design.
- Concurrent worktree WIP exists outside this step and was not edited or included in this step.
