---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
step_id: 'S16'
related:
  - "[[2026-06-13-first-filer-attestation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace first-filer-attestation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# Add a real-storage test proving the gate fails closed when the profile carries no activity_start_date and that the non-blocking advisory surfaces when a declared date scopes a requirement out

## Scope

- `src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py`

## Description

- Add `test_verify_fails_closed_when_profile_records_no_activity_start_date`: a profile with no `activity_start_date` against M390/2025 (priors missing) surfaces the BLOCKING fail-closed finding and refuses the grant.
- Add `test_verify_surfaces_operator_declared_suppression_advisory_without_blocking`: a declared date (2025-10-01) scopes 1T/2T/3T out as non-blocking WARNING advisories while the in-scope 4T still blocks.

## Outcome

- Landed in commit `0c69ec483`. Both real-storage tests pass through the live `verify_modelo_revision` path. The advisory test confirms WARNING severity for each suppressed quarter and that only the in-scope 4T produces a blocking cross-period finding.

## Notes

- The advisory test deliberately leaves 4T in scope so the report returns (granted False) rather than reaching the workflow build-stage gate.
