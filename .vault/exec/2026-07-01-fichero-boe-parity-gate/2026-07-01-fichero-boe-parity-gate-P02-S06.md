---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-01'
modified: '2026-07-08'
step_id: 'S06'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# Unit-test the rendered-set enumeration across CASILLA, BINDING-row and COMPUTED field kinds

## Scope

- `src/aeat/application/filing/tests/test_export_rendered_casilla_set.py`

## Description

- Add `test_export_completeness_sets.py` cases: the representable set covers every non-suppressed CASILLA field; the rendered set equals `representable ∩ draft.values` and is a subset of representable; dropping a required casilla from the draft removes it from the rendered set (the thin-file signal at the derivation level).

## Outcome

Four tests pass (90s). Ruff clean.

## Notes

One first-pass failure was a test-assumption bug, not a helper bug: the initial assertion computed the CASILLA-field set over all records, ignoring disposition suppression, so it disagreed with the helper (130 carries a suppressed DID page under a non-refund header). Fixed by mirroring `_did_page_suppressed` in the expected-set computation. The helper was correct.
