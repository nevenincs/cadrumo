---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S14'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---




# Add a real-storage test proving the activity-start scoping applies uniformly to both previous_filing and relation_source_requirements origins

## Scope

- `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`

## Description

- Add `test_activity_start_scoping_applies_to_both_requirement_origins`: real-storage M180/0A (M115 registry-relation origin) and M303/4T (M303 previous_filing origin) both suppress their strictly-prior quarters under a declared activity-start date.

## Outcome

- Landed in commit `0c69ec483`. Relation origin suppresses `{1T,2T}` (all REGISTRY_RELATION); the M303/4T period suppresses `{3T}` carrying BOTH the previous_filing binding and the self-compensacion registry relation, proving uniformity across origins on the same period.

## Notes

- The M303 self-compensacion carve-out naturally exercises both origins on one period.
