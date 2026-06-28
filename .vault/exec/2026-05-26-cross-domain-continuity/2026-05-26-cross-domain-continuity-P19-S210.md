---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S210
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity P19.S210 — provenance re-validation drift detection

## Outcome

Added `StoredCalculationDriftError` and `_assert_revision_content_integrity` to
`src/aeat/application/modelo/_actions.py`.

`_assert_revision_content_integrity` performs two checks:

1. **Content-hash check** — re-derives the SHA-256 `calculation_revision_id` from the
   stored `(work_unit_id, inputs_snapshot, binding_overrides, casilla_values,
   source_transaction_ids, borrador fields)` and compares against the persisted id.
   A mismatch raises `StoredCalculationDriftError`.

2. **Observation provenance cross-check** — for each typed `CasillaObservation` in
   `revision.observations`, asserts `obs.value == casilla_values[obs.casilla_id]`.
   A mismatch raises `StoredCalculationDriftError`.

The function is called in `verify_modelo_revision` after loading the revision and
checking state, before any finding collection.

`StoredCalculationDriftError` is exported from `src/aeat/application/modelo/__init__.py`.

## Files changed

- `src/aeat/application/modelo/_actions.py` (`StoredCalculationDriftError`, `_assert_revision_content_integrity`, wiring in `verify_modelo_revision`)
- `src/aeat/application/modelo/__init__.py` (export `StoredCalculationDriftError`)
