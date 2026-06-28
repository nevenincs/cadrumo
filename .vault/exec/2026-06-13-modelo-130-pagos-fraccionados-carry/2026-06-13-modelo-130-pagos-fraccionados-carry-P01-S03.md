---
tags:
  - '#exec'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S03'
related:
  - "[[2026-06-13-modelo-130-pagos-fraccionados-carry-plan]]"
---




# add a selector unit test asserting the expanding-span mode emits the correct anchor set per target (1T empty, 2T={1T}, 3T={1T,2T}, 4T={1T,2T,3T}) and that the collision gate plus _is_direct_previous_filing_binding classify it as a direct previous_filing binding, computing expected anchors by an independent enumeration not the selector method under test

## Scope

- `src/aeat/domain/calculations/registry/tests/test_bindings_previous_filing.py`

## Description

- Added selector unit tests asserting the per-target anchor set (1T empty / absent-by-design, 2T={1T}, 3T={1T,2T}, 4T={1T,2T,3T}), with the expected anchors built by an independent enumeration of the strictly-preceding same-ejercicio quarters rather than by calling the selector method under test.
- Added coverage asserting the span mode is classified a direct `previous_filing` binding by `_is_direct_previous_filing_binding` and accepted by the relation-source collision gate `validate_slot_source_hygiene` without a carve-out, plus the mutual-exclusivity validation rejections from S02.

## Outcome

13 selector unit tests cover the expanding-span anchor emission, the empty-1T absent-by-design recognition, the direct-previous_filing classification, the collision-gate acceptance, and the mutual-exclusivity guards; the expected anchor sets are independently enumerated, so the test is non-tautological against the selector. Landed in commit `6c25cd69a`.

## Notes

Per `no-tautological-calculation-tests`, the expected anchor sets are derived by hand-enumerated strictly-preceding quarters, not by re-invoking `_prior_quarter_expanding_span_anchors`; a selector that emitted a wrong span (off-by-one, included the target, or crossed the ejercicio boundary) would fail loudly.
