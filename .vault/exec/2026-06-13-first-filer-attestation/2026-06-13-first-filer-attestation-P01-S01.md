---
tags:
  - '#exec'
  - '#first-filer-attestation'
date: '2026-06-13'
step_id: 'S01'
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
