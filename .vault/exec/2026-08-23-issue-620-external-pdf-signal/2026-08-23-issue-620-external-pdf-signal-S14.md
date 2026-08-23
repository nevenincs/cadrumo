---
tags:
  - '#exec'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:0833d92515ed84bb7c75de41c79ab2c863ce95040b98f7661395e5e2fe864d35'
step_id: 'S14'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-plan]]"
---

# Verify authority adjudication through only the affected registry and parser unit modules

## Scope

- `src/cadrumo/tests/fixtures/external_layout_candidates/tests/`
- `src/cadrumo/adapters/inbound/declaracion/tests/test_external_layout_candidate_matrix.py`

## Description

- Run Ruff against the candidate contract, its contract tests, the cross-model
  matrix, and the M130 external-layout boundary.
- Run only the three authorized unit modules with in-process execution.
- Replace the stale legacy-authority assertion in
  `src/cadrumo/adapters/inbound/declaracion/tests/test_parser_boundary_m130_external_layout.py`
  with the accepted three-axis M130 verdict and continued non-enrolment checks.
- Rerun the exact Ruff and pytest boundaries after the verification correction.

## Outcome

- Ruff passed across all four requested Python paths.
- The final three-module pytest gate passed all 59 tests in 52.26 seconds.
- Both M130 candidates prove third-party artifact authenticity, verified
  official-base derivation, current applicability to `2019-y-siguientes`, and
  non-enrolment while still discovering 19 blank boxes without fabricated
  values.

## Notes

- The initial exact pytest run produced 57 passes and two failures. Both failures
  were the plain/fillable variants reaching a removed
  `source_chain.authority_status` field after the accepted S12 migration.
- No production or candidate-corpus file was changed.
