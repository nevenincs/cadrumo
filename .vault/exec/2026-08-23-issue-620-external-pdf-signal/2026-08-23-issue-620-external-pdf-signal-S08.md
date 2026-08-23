---
tags:
  - '#exec'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:8fce85f2d7d4273d870d0c16d3b369dd3c85f13af19da14f44e4cc8556a0c4b9'
step_id: 'S08'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-plan]]"
---

# Add the cross-model external-layout outcome matrix with explicit unsupported and unavailable results

## Scope

- `src/cadrumo/adapters/inbound/declaracion/tests/test_external_layout_candidate_matrix.py`

## Description

- Drive both plain and fillable candidates through the production extraction classification primitives.
- Record exact typed outcomes for Modelos 130, 131, 303, 036 and 349.
- Assert exact value, missing, malformed and ambiguous buckets and zero fabricated values.
- Keep the unsupported Modelo 131 layout and unavailable Modelo 036 snapshot visible rather than omitting them.

## Outcome

The ten-row matrix reports both M130 variants as `blank_no_values` with all 19 targets missing; both M131 variants as `unsupported_layout` with 13 exact malformed targets and ambiguous casillas 03 and 05; both M303 variants as `blank_no_values` with 12 exact missing targets; both M036 variants as `unavailable_registry_snapshot`; and both M349 variants as `blank_no_values` with all four targets missing at valid period `01`.

Every row asserts an empty extracted-value bucket. Ruff passed for the new module, and its focused unit run passed 11 tests in 55.73 seconds.

## Notes

No production parser or registry code changed. The matrix reports measured parser compatibility only; the candidates remain unverified external layouts and do not become AEAT authority.
