---
tags:
  - '#exec'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
step_id: 'S10'
related:
  - "[[2026-06-13-modelo-130-pagos-fraccionados-carry-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace modelo-130-pagos-fraccionados-carry with a kebab-case feature tag, e.g. #foo-bar.
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

# teach the observation-coverage validator to treat an empty span as satisfied (not a missing required observation) so a first filer fires no blocker, extending previous_filing_observation_requirements anchor derivation

## Scope

- `src/aeat/domain/calculations/registry/_validate_previous_filing_sources.py`

## Description

- Confirmed the observation-coverage validator (`previous_filing_observation_requirements`) treats an empty span as satisfied: at 1T it emits NO casilla-05 requirement, so a genuine first filer fires no missing-observation blocker.
- Added `test_validate_previous_filing_sources.py` asserting the empty-span (1T) emits no casilla-05 requirement and 2T/3T/4T emit exactly the expanding prior-quarter set.

## Outcome

The coverage validator never demands a prior-quarter observation the empty span does not declare. Verified by `test_validate_previous_filing_sources.py` (3 passed, commit `53de169cb`).

## Notes

The P01 anchor enumeration already returns the empty span at 1T, so the validator inherits the empty-satisfied behaviour without modification; the test pins it.
