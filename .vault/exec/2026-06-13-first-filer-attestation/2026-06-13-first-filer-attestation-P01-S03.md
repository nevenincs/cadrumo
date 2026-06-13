---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
step_id: 'S03'
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
