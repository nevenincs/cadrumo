---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S13'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---




# Prove identical latest selection and history ordering across all capture routes, their distinct failure policies, and preservation of the separate strict IVA compensation persistence path

## Scope

- `src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py`

## Description

- Retarget the pre-existing incomplete-observation test onto the finalizer: `test_filed_capture_best_effort_finalizer_reports_incomplete_observation` proves BEST_EFFORT accumulates a typed `SedeParseError` failure with `keys == ()` and writes nothing.
- Add `test_filed_capture_fail_fast_finalizer_raises_on_incomplete_observation`: FAIL_FAST raises `LiveApplicationError` on the same incomplete observation and persists nothing — proving the distinct single/source policy.
- Add `test_all_capture_routes_share_one_selection_and_ordering_authority`: a duplicate-period (later BAJA cannot supersede an earlier ALTA) cross-year batch resolves the SAME ordered keys via both `finalize_filed_capture` and `persist_latest_filed_calculation_observations` (`("303:2025:4T", "303:2026:1T")`), proving the finalizer and the calculation-history path cannot drift.
- Add `test_finalizer_does_not_disturb_the_separate_strict_iva_compensation_path`: the strict IVA compensation persistence remains a distinct function with its own reload-verification contract, not collapsed by the consolidation.

## Outcome

Real-behavior against encrypted secure storage (`_secure_backend`), no mocks: identical latest-selection and history ordering across routes, the distinct fail-fast vs best-effort failure policies, and preservation of the separate strict IVA compensation path are all proven. Full application/live suite: 185 passed; ruff clean.

## Notes

The cross-route parity test compares the finalizer's keys against the calculation-history persistence route's keys directly (same shared selector), so it fails if either route reintroduces its own selection/ordering. The ordering divergence the old capture-side loop carried (raw `registry_token` vs the fiscal/numeric history-period key) is closed structurally by the single shared authority; the two are homogeneous for single-modelo quarterly periods but can no longer drift.
