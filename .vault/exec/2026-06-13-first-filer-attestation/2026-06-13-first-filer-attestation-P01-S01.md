---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S01'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---




# Add the NO_PRIOR_OBLIGATION_PRE_ACTIVITY provenance facet kind enum to the cross-period clean-state vocabulary while gate-proving it never enters _OFFICIAL_SOURCE_KINDS

## Scope

- `src/aeat/application/calculations/_cross_period_clean_state.py`

## Description

- Add the `NoPriorObligationProvenanceKind` `StrEnum` to the cross-period clean-state vocabulary, carrying the facet discriminator `NO_PRIOR_OBLIGATION_PRE_ACTIVITY` plus the `OPERATOR_DECLARED` / `CENSO_CORROBORATED` provenance members.
- Document that the discriminator names a suppression, not an evidence source, so it is categorically excluded from `_OFFICIAL_SOURCE_KINDS`.

## Outcome

- Landed in commit `4026deb0d`. The enum is exported through `aeat.application.calculations`. The exclusion is gate-proven by the P04.S17 honesty regression (`test_no_prior_obligation_provenance_never_enters_official_source_kinds`), which asserts every member value is absent from `_OFFICIAL_SOURCE_KINDS`.

## Notes

- `_OFFICIAL_SOURCE_KINDS` is never weakened. The enum value strings are deliberately disjoint from the official-evidence set.
