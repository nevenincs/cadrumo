---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:e87c40ee45e0c5d1751e9d9b6dc3bd5707279ad539207a6e295fd7ec32feb796'
step_id: 'S12'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# Introduce one typed filed-capture finalizer and failure accumulator used by single, bulk, and source capture with explicit fail-fast single and source policy and best-effort bulk policy

## Scope

- `src/cadrumo/application/live/_filed_capture_finalizer.py`

## Description

- Add `_filed_capture_finalizer.py` with one typed finalizer for filed-declaration calculation-history enrollment.
- Add the closed `FiledCaptureFailurePolicy` StrEnum: `FAIL_FAST` (single + source capture — abort on the first registry-enrollment failure) and `BEST_EFFORT` (bulk capture — accumulate failures, keep persisting).
- Add the typed `FiledCaptureFinalization` result carrying `calculation_observation_keys` and `failures`.
- Add `finalize_filed_capture(observations, *, justificante_csvs_by_observation, policy)`: delegates selection + history ordering to the persistence authority's `select_latest_filed_observations_in_history_order`, persists each latest observation via `persist_filed_calculation_observation`, accumulates typed `FiledDataCaptureFailureRow` failures, and under `FAIL_FAST` raises the first accumulated failure as a `LiveApplicationError`.
- Move the failure-row builder and the fail-fast raiser (`_filed_registry_enrollment_failure_row`, `_raise_registry_enrollment_failure`) into this module as the finalization-failure owner.

## Outcome

Single, bulk, and source capture now share ONE finalizer and ONE failure accumulator with explicit per-route policy, replacing the capture module's inline selection+persistence loop. The fail-fast raise preserves the exact prior behaviour (raise the first failure with count + context); best-effort preserves the prior accumulate-into-report behaviour. 30 tests pass in the calculation-history test file; ruff clean.

## Notes

RAG-first confirmed the persistence authority as the canonical owner before adding the finalizer (no parallel selection authority introduced). The finalizer is an intra-package private module consumed by `_filed_data_capture.py`; no cross-package facade export is needed. Distinct-policy behaviour is proven under S13.
