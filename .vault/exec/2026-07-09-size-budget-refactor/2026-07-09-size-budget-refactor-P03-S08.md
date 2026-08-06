---
tags:
  - '#exec'
  - '#size-budget-refactor'
date: '2026-07-09'
modified: '2026-07-17'
body_hash: 'sha256:d408b2659f8dd3361899d02e02ac78c86a4fa9d8281f21a9f7e24851b8b0f583'
step_id: 'S08'
related:
  - "[[2026-07-09-size-budget-refactor-plan]]"
---

# Extract the identified cohesive chunk into private helper functions in the same module, preserving the public API and behavior exactly

## Scope

- `src/aeat/domain/deadlines/_profiles.py`

## Description

- Extracted `_canonicalize_and_pad` and `_objective_estimation_fields` as private module-level helpers in `_profiles.py`, called from `taxpayer_profile_from_mapping` in place of the two inlined blocks.
- Preserved the function signature and return value exactly: every field is computed from the same inputs in the same order as before the split.
- Landed as commit `ccd5e2057` ("refactor(deadlines): split taxpayer_profile_from_mapping under the size budget"): 204 lines changed (124 insertions, 80 deletions) in `src/aeat/domain/deadlines/_profiles.py`.

## Outcome

`taxpayer_profile_from_mapping` shrank from 196 to 118 lines (default budget 180). No behavior change.

## Notes

Landed by coder-perf (parallel P03 assignment per the plan's Parallelization section); this record documents the completed Step for plan-closure purposes per `plan-closure-requires-exec-records`.
