---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:2c550d05f74f7d0e073d2ea60b7b897003450fe07d320305194b6feba843bda4'
step_id: 'S46'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Expose missing source diagnostics in modelo calculation errors

## Scope

- `src/aeat/application/modelo/_actions.py`

## Description

- Verify-and-close: the modelo calculation path already exposes missing-source diagnostics at HEAD.
- Confirm `collect_unhandled_source_diagnostics` runs on the live calculate path and its output is appended to `source_diagnostics` on the persisted result.
- Confirm `BucketAggregationCalculationResult.source_diagnostics` carries the `CalculationSourceDiagnostic` rows (reason `unhandled_binding_source`) with the binding id and message, and `assert_no_novel_source_kinds` raises for an unaccounted source.

## Outcome

- Requirement satisfied at HEAD; no code change needed. The plan's target `_actions.py` was split into `_calculation_actions.py` during the test-topology/refactor era; the wiring lives there (unhandled diagnostics collected and merged onto the result; novel-source gate asserted before aggregation).
- Gate evidence green: `test_source_boundary_and_enrollment.py::test_s08_source_diagnostics_carries_advisory_for_deferred_source` and `::test_s08_..._for_atribucion_member` prove a deferred/unrouted source surfaces a non-blocking advisory on `result.source_diagnostics` rather than a silent blank.

## Notes

- The diagnostics are NON-blocking: the revision is computed and persisted, and the advisory is surfaced so an unrouted source is not silently under-declared (`no-silent-under-declaration`). Blocking behavior for a truly novel (unaccounted) source is the separate `ModeloAggregationBindingError` raise, covered by the S48 test.
