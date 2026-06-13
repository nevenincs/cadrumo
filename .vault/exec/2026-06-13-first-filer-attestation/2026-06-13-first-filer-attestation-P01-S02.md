---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S02'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---




# Add the typed NoPriorObligationProvenance model carrying activity_start_date, provenance kind (operator-declared vs censo-corroborated), and optional censo snapshot id

## Scope

- `src/aeat/application/calculations/_cross_period_clean_state.py`

## Description

- Add the typed `NoPriorObligationProvenance` pydantic model carrying `facet_kind`, `activity_start_date`, `provenance_kind`, and an optional `censo_snapshot_id`.
- Validate that `provenance_kind` is `OPERATOR_DECLARED` / `CENSO_CORROBORATED`, and that censo-corroborated provenance requires a snapshot id.

## Outcome

- Landed in commit `4026deb0d`. Strict-frozen, exported through `aeat.application.calculations`. The `is_operator_declared` property drives the non-blocking advisory. Validation verified directly (operator-declared default; censo requires snapshot id; facet discriminator rejected as provenance kind).

## Notes

- The model separates the facet-kind discriminator from the provenance kind so the auditable record is unambiguous.
