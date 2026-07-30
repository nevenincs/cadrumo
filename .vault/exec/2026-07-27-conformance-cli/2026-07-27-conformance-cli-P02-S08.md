---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S08'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# re-point the export completeness and fichero-BOE parity tests at the shared required-set derivation, removing the mirrored duplicate

## Scope

- `src/cadrumo/application/filing/tests`

## Description

- In `test_export_completeness_gate.py`: added `required_applicable_casilla_ids` to the `_export` import; replaced the `_required_applicable` helper body (which re-derived the set comprehension verbatim with an "Mirror the gate's required set" comment) with a thin delegate calling the shared function. Changed return type annotation from `set[CasillaId]` to `frozenset[CasillaId]` to match the shared function.
- In `test_fichero_boe_completeness_parity.py`: added `required_applicable_casilla_ids` to the `_export` import; replaced the inline three-line set comprehension in `test_complete_draft_reaches_disk_for_every_required_casilla` (including its "Mirror the gate's required set" comment) with a single call to the shared function.

## Outcome

Both test modules compile cleanly and all 12 tests pass. Mutation-flip evidence: temporarily corrupting `required_applicable_casilla_ids` to return `frozenset()` caused 3 failures — `test_thin_fixed_width_draft_panics_before_writing[modelo-130]`, `test_thin_fixed_width_draft_panics_before_writing[modelo-390]`, and `test_complete_draft_reaches_disk_for_every_required_casilla` — confirming the tests are non-vacuous. Reverting the mutation restores 12 passed. Commit: `9c64ec0d99`.

## Notes

Landed in the same commit as S07 because the test re-pointing depends on the extraction.
