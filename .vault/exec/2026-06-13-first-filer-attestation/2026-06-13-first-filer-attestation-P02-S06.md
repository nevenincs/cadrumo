---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S06'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---




# Apply the same activity-start scoping filter to registry-relation-origin requirements so the suppression is uniform across both previous_filing and relation_source_requirements origins

## Scope

- `src/aeat/application/calculations/_cross_period_clean_state.py`

## Description

- Apply the same `partition_cross_period_requirements_by_activity_start` filter to registry-relation-origin requirements (the predicate reads `requirement.period`, which both origins carry), so suppression is uniform across `previous_filing` and `relation_source_requirements`.

## Outcome

- Landed in commit `4026deb0d`. Proven by the P04.S14 uniformity test: M180/0A (M115 relation origin) suppresses its pre-activity quarters identically, and the M303/4T self-compensacion period suppresses BOTH its previous_filing and registry_relation origins under one date.

## Notes

- A first filer is never unblocked on one origin while trapped on the other.
