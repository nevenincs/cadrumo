---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S07'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---




# Stamp each suppressed requirement with the no-prior-obligation provenance facet and resolve its binding value through the existing absent-by-design path to a provenance-marked Decimal zero rather than an unstamped carry

## Scope

- `src/aeat/application/calculations/_cross_period_clean_state.py`

## Description

- Add `_suppressed_pre_activity_evidence`, which builds the clean, facet-stamped `CrossPeriodDependencyEvidence` row for a suppressed requirement: no observation loaded, no blockers, a provenance-marked zero via the absent-by-design path.

## Outcome

- Landed in commit `4026deb0d`. Each suppressed requirement is stamped with `NoPriorObligationProvenance` (operator-declared, the scoping date). Proven by P04.S12 asserting every suppressed row carries the facet with the correct date and `OPERATOR_DECLARED` provenance and empty blockers.

## Notes

- A suppressed pre-activity period has no observation to stamp, so the carry resolves to a provenance-marked zero, never an unstamped carry (`carried-observations-stamp-their-revision` satisfied).
