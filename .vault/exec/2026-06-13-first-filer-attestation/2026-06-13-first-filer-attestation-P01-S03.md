---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S03'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---




# Add the suppressed no_prior_obligation facet field plus its clean-property treatment to CrossPeriodDependencyEvidence so a scoped-out requirement is explicit and non-silent

## Scope

- `src/aeat/application/calculations/_cross_period_clean_state.py`

## Description

- Add the `no_prior_obligation: NoPriorObligationProvenance | None` facet field to `CrossPeriodDependencyEvidence`.
- Add the `suppressed_pre_activity` and `operator_declared_suppression_advisory` evidence properties and the verdict-level `suppressed_pre_activity_dependencies` / `has_operator_declared_suppression_advisory` rollups.

## Outcome

- Landed in commit `4026deb0d`. A suppressed dependency carries no blockers (stays `clean`) but is explicit and auditable via the facet, satisfying `no-silent-under-declaration`. Verified by the P04.S12 test asserting every suppressed row has empty blockers and a populated facet.

## Notes

- The facet is `None` for an in-scope dependency, so existing evaluated rows are unchanged.
