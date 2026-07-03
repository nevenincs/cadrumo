---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-06-30'
step_id: 'S17'
related:
  - "[[2026-06-26-binding-fold-in-carry-unification-plan]]"
---

# vaultspec-code-reviewer: assert the live EnrollmentRecorder remains intact and importable through the top-level __all__ re-export and the full collect-only gate is clean after the orphan deletion

## Scope

- `src/aeat/application/calculations/tests/test_multi_year.py`

## Description

- Assert the live `EnrollmentRecorder` (and the co-located `EnrollmentEvidence` / `EnrollmentYearObservation` / `EnrollmentEvidenceError` / `assert_enrollment_matches_manifest`) and the live `PreviousFilingSourceResolver` remain intact and importable through the package re-export after the orphan deletion, and that the full collect-only gate is clean.

## Outcome

- The live concerns import cleanly through the package facade; `MultiYearResolver` correctly raises `ImportError`. collect-only is clean. The source-resolver enrollment gate accepts the now-empty known-non-mesh inventory, `test_carry_gate_parity` (the live-path R2 coverage) passes, and the full calculations plus M390 FIFO plus retenciones suites pass (424 tests). No casilla value shifted.

## Notes

- The R2 carry-gate coverage that the two deleted `MultiYearResolver` tests provided is preserved by the live-path tests in `test_carry_gate_parity` (the `_revision_prefill_divergence` gate across the matching / divergent / missing / indeterminate outcomes), so removing the redundant secondary coverage lost no enforcement.
