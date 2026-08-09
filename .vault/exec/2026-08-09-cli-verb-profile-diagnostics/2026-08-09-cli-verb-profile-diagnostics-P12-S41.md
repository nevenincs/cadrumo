---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:d8af4d60ee101868c326a87ac58637f2c73d5fd53a9c41a031ea5b7a97f6ea2a'
step_id: 'S41'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Resolve the unsatisfied date binding to the profile facts it consumes and name those in the calculate guidance, degrading to the binding id when it cannot be resolved

## Scope

- `src/cadrumo/entrypoints/cli/_modelo.py`

## Description

- Added `_date_binding_profile_requirements`, resolving the work unit's snapshot, matching the unsatisfied binding, extracting the profile keys it consumes, and rendering them as grounded requirement rows.
- Replaced the binding id in the guidance with that rendering, and updated the locale string across all four catalogues.

## Outcome

The guidance names the profile fact the operator has to set, instead of a registry binding id that appears nowhere in the profile editor.

The instruction was actively misleading before: it said "Set <binding id> on the active profile", and the binding id is not something a profile can hold. An operator following it literally had nothing to act on.

Degradation is deliberate and follows the sibling source lookup already in this module: an absent work unit, an unresolvable snapshot, or an unmatched binding id returns the binding id, which is the guidance this surface gave before. A degraded message is worse than a resolved one and better than none.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_missing_date_binding_guidance_grounding.py -n 0 -q
    3 passed in 11.32s

## Notes

The first implementation rendered these keys through the SELECTOR renderer, which resolved nothing. That defect and its correction are recorded under the following Phase.
