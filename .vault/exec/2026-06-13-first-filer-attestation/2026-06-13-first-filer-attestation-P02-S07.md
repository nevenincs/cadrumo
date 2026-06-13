---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
step_id: 'S07'
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

# Stamp each suppressed requirement with the no-prior-obligation provenance facet and resolve its binding value through the existing absent-by-design path to a provenance-marked Decimal zero rather than an unstamped carry

## Scope

- `src/aeat/application/calculations/_cross_period_clean_state.py`

## Description

- Add `_suppressed_pre_activity_evidence`, which builds the clean, facet-stamped `CrossPeriodDependencyEvidence` row for a suppressed requirement: no observation loaded, no blockers, a provenance-marked zero via the absent-by-design path.

## Outcome

- Landed in commit `4026deb0d`. Each suppressed requirement is stamped with `NoPriorObligationProvenance` (operator-declared, the scoping date). Proven by P04.S12 asserting every suppressed row carries the facet with the correct date and `OPERATOR_DECLARED` provenance and empty blockers.

## Notes

- A suppressed pre-activity period has no observation to stamp, so the carry resolves to a provenance-marked zero, never an unstamped carry (`carried-observations-stamp-their-revision` satisfied).
