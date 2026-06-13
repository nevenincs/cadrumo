---
step_id: S271
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W02.P11.S271 — Survivor envelope enrollment test

## Scope

Add `src/aeat/application/test_survivor_envelope_enrollment.py` with
real-behavior tests asserting that every application-layer survivor error
class is `ERROR_REGISTRY`-enrolled and round-trips through
`build_error_envelope`.

## Outcome

### New test file

`src/aeat/application/test_survivor_envelope_enrollment.py` — 8 tests:

- `test_repository_setup_error_enrolled` — S266 class, code `FAIL_STORAGE_REPOSITORY_SETUP`
- `test_profile_label_ambiguous_error_enrolled` — S267, code `REFUSED_PROFILE_LABEL_AMBIGUOUS`
- `test_repair_integrity_error_enrolled` — S268, code `INTEGRITY_REPAIR_INTEGRITY`
- `test_repair_decision_not_found_error_enrolled` — S268, code `FAIL_REPAIR_DECISION_NOT_FOUND`
- `test_repair_decision_not_found_is_subtype_of_repair_integrity` — hierarchy structural check
- `test_snapshot_not_found_error_enrolled` — S269, code `FAIL_SNAPSHOT_NOT_FOUND`
- `test_snapshot_not_found_subclasses_still_work` — MRO / KeyError compat check
- `test_modelo_applicability_filter_error_enrolled` — pre-existing class, coverage baseline

All 8 pass. No mocks, skips, or tautological assertions.

## Files touched

- `src/aeat/application/test_survivor_envelope_enrollment.py` (new)

## Test outcome

`pytest src/aeat/application/test_survivor_envelope_enrollment.py` — 8 passed, 0 failed.

## Collision signal

No files pre-existed; new file only.
