---
tags:
  - '#exec'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
step_id: 'S06'
related:
  - "[[2026-06-21-crossperiod-filing-deadlock-plan]]"
---




# Add the non_official_local_chain_advisory facet on CrossPeriodDependencyEvidence and the has_non_official_local_chain_advisory verdict property

## Scope

- `src/aeat/application/calculations/_cross_period_clean_state.py`

## Description

- Add the `non_official_local_chain_advisory: bool = False` field on `CrossPeriodDependencyEvidence`, mirroring the existing `unstamped_revision_advisory` facet pattern.
- Add the `has_non_official_local_chain_advisory` aggregate property on `CrossPeriodCleanStateVerdict`.

## Outcome

Landed in commit `84add274d`. The typed marker yields a clean (advisory-only) evidence row idiomatically, following the `NoPriorObligationProvenance` facet shape.

## Notes

