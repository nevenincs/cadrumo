---
tags:
  - '#exec'
  - '#profile-requirement-grounding'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:8a528cb284d5cedb1925bd57533616e5a52577f8bf7a118acad090ee62915358'
step_id: 'S02'
related:
  - "[[2026-08-08-profile-requirement-grounding-plan]]"
---

# Populate the new fields in ProfilePreflightService.report() from the in-scope field object unioned with build_profile_grounding_index

## Scope

- `src/cadrumo/application/user_profile/_preflight.py`

## Description

Populated the three new fields in `ProfilePreflightService.report()` (`_preflight.py`). Initial version folded the caller's target `modelo` into `modelos` and read `field.description` as the label; both were corrected after the P04.S10 code review. Final shape: a shared `_requirement()` builder resolves `label` via `profile_field_label(section_key, field)` (falling back to the selector only when the field is not in the schema), unions `legal_refs` from the schema field and from `build_profile_grounding_index` when an `authority` is supplied, and sets `modelos` to the grounding index's consuming-modelo set only - never the call's target modelo.

## Outcome

Delivered narrower than first checked, then corrected same-session. The first pass (checked as part of `P01`) used `field.description` for the label and folded the target modelo into `modelos`; the P04.S10 review found both wrong and they were fixed before `P04.S11`. The final state is what this record describes; the intermediate wrong state was never separately recorded because it was corrected within the same session before any external consumer could observe it.

## Verification

`pytest src/cadrumo/application/user_profile/tests/ src/cadrumo/application/modelo/tests/test_profile_readiness_gate.py -n 0 -m "unit or integration"` - 597 passed, sequential run (per this project's own guidance to re-run sequentially before triaging a parallel-run failure).

## Notes

See `2026-08-09-profile-requirement-grounding-audit` findings `label-bypasses-canonical-resolver`, `grounding-union-dropped-on-baseline-and-validation-rows`, and `modelos-field-carries-two-different-meanings` for the full before/after.
