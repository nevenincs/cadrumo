---
tags:
  - '#exec'
  - '#registry-temporal-coverage'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:0871253ded858a689dc13d23ec28043cb4c5ed106f6f1ec18b552a5d6f9d612c'
step_id: 'S03'
related:
  - "[[2026-08-14-registry-temporal-coverage-plan]]"
---
# Enforce the disposition-conditional grade ladder in registry build validation, registered in the family dispatch table: a calculation claim with an empty applicable formula family refuses and an informative revision at filing grade with a reasoned not_applicable formula family passes

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Trace the authority-grade ladder from its introduction in `a16b0b8ffd7` through the absence-refusal strengthening in `a650f9bd9d5`; both commits are ancestors of the current `HEAD`.
- Inspect `validate_authority_grade_section` and the `validate_revision_definition` registry-build dispatch that appends its accumulated failures.
- Verify the rung semantics against the real registry corpus: an absent grade refuses, declared applicability remains scheduling-only, calculation requires a resolved formula family, and filing requires every enrolled family to be resolved or honestly not applicable.
- Run the focused authority-grade ladder and revision-authority-grade suites.

## Outcome

The required S03 enforcement is already present in the live registry-build path and its focused evidence passes: 18 tests passed. The validator is registered in the per-revision build dispatch, derives family state from the coverage manifest, and preserves the distinction between a reasoned `not_applicable` family and `blocked_pending_evidence`. This record restores the missing execution evidence without changing production behavior.

## Notes

No production or test files changed. The temporal-plan S03 row remains open intentionally: its independent review is owned by the roll-up W01.P01.S04, and only the subsequent reconciliation step may close the temporal row.
