---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:87748d6db41525811be20b685787a5bfae58ca97a3509738292ba7552737c07f'
step_id: 'S35'
related:
  - '[[2026-08-14-registry-temporal-coverage-plan]]'
  - '[[2026-08-14-registry-campaign-sequencing-audit]]'
---

# Rename the five production identifiers in the annual-orden projection models that carry a plan step id, being the coordinate-completeness validator and the four validators it calls, to names describing what they check, because the source-hygiene rule forbids waves, phases, issue workflow and other project-management metadata in production identifiers and these names go stale the moment the plan that named them closes

## Scope

- `src/cadrumo/domain/calculations/registry/_m303_orden_projection_models.py`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

This record documents work found already present, uncommitted, in the working
tree at the time of writing; it is written retrospectively from the code, not
from having performed the implementation.

The five identifiers in `_m303_orden_projection_models.py` carry no `s59` (or
`S59`) token anywhere in the file, confirmed by a case-insensitive grep of the
module returning zero matches. The coordinate-completeness validator (the
`@model_validator(mode="after")` on `M303RegimenSimplificadoSnapshot`) is named
`_coordinates_are_complete_and_source_pinned`, and the four validators it calls
are `_validate_regimen_simplificado_record_design`,
`_validate_regimen_simplificado_coordinate`,
`_validate_regimen_simplificado_agricultural_authority` and
`_validate_regimen_simplificado_2022_coordinate` (the last called conditionally,
only when `filing_year == 2022`) — five descriptive names, none referencing a
plan step id.

## Outcome

Every remaining `S59` occurrence in the tree (grepped case-sensitively across
`src/`) is a legitimate AEAT casilla/coordinate reference — "the exact S59
Orden and record-design snapshot", "S59 DP30302 authority", "S59 constructors
must explicitly pass the canonical annual-Orden fields" — in
`domain/modelos/_calculation_revision_m303_handoff.py`,
`domain/iva/tests/test_regimen_simplificado_constructor_census.py`,
`application/modelo/_m303_regimen_simplificado_scope.py`,
`application/modelo/_m303_filing_evidence.py` and
`application/filing/tests/test_m303_regimen_simplificado_evidence_projection.py`.
None of these name the renamed validators; they describe the AEAT "S59"
scope/coordinate concept, which the row does not ask to rename.

Verification: `pytest src/cadrumo/domain/calculations/registry/tests/ -k "orden_projection or m303_orden" -n 0 -q`
→ `9 failed, 20 passed` in 260.80s. All 9 failures are
`RegistryValidationError: modelo 303 revision ... is 'pending_review'; filing-grade
snapshot requires operator_reviewed revision` — the same tree-wide review-status
collision recorded in this same day's registry-campaign-sequencing audit
(linked in `related:`) and in this record's sibling `W01.P02.S04` record, not a
defect in the renamed validators.
The 20 passing tests exercise `M303RegimenSimplificadoSnapshot` and
`M303AnnualOrdenSnapshot` construction and their validators directly, so the
renamed identifiers are confirmed live and functioning under their new names.

## Notes

This record documents work found already present on disk from a prior working
session and does not represent implementation performed by the agent writing
this record. The work is UNCOMMITTED at the time of writing (`git status` shows
`_m303_orden_projection_models.py` as modified, unstaged).

This row's deletion-inventory consumption is none — it renames identifiers, it
deletes no surface.
