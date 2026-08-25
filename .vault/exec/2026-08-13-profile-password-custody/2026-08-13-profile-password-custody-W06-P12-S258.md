---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:b2107215c7db8c94e1b6908cd6b0a441a09d1310714c81603a1c4833d3886c8d'
step_id: 'S258'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Make registry referential-integrity preflight validate every revision at its declared authority grade while retaining full reference checks and real invalid-reference failures across applicability, calculation, and filing revisions

## Scope

- `src/cadrumo/application/preflight.py and src/cadrumo/application/tests/test_preflight.py`

## Description

- Verify the preflight snapshot call passes each revision's effective authority grade.
- Exercise real applicability, calculation, and filing revisions and assert exact observed grades.
- Retain fail-closed behavior for an ungraded revision and a catalogue with dangling legal references.
- Re-run the complete preflight module and the real `config check` preflight projection.

## Outcome

Referential-integrity preflight validates every representative bundled revision at its declared grade instead of imposing the filing floor on applicability and calculation records. Missing grades and invalid references remain errors.

The five focused grade/reference and structural regressions pass, the full 21-test preflight module passes, the integration-marked `config check` row passes, and Ruff and ty pass on both owning files.

## Notes

Production and regression provenance is concurrent commit `963bc7ef12`; this Step closure records its verification rather than duplicating the implementation.

Formal review first rejected monkeypatched and stubbed proofs, then identified that runtime counts alone did not bind the snapshot keyword. The final suite uses real authority objects plus an AST gate that requires the production snapshot call to consume the same `requested_grade` local bound from `revision.effective_authority_grade`.
